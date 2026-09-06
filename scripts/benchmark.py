import argparse
import http.client
import json
import math
import statistics
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

RATE_LIMIT_GUIDANCE = (
    'The shorten endpoint rate limit was reached. For a local Docker load test, run:\n'
    '  TRIMLY_WRITE_RATE=10000/min docker compose up -d --force-recreate web\n'
    'Then run the benchmark again. Restore the default afterward with:\n'
    '  docker compose up -d --force-recreate web'
)


@dataclass(frozen=True)
class RequestResult:
    status: int | None
    elapsed_seconds: float
    body: bytes = b''
    error: str | None = None


class BenchmarkClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            raise ValueError('Base URL must start with http:// or https://.')
        if parsed.query or parsed.fragment:
            raise ValueError('Base URL must not contain a query string or fragment.')

        self.scheme = parsed.scheme
        self.host = parsed.hostname
        self.port = parsed.port
        self.root_path = parsed.path.rstrip('/')
        self.timeout = timeout
        self._local = threading.local()

    def _connection(self) -> http.client.HTTPConnection:
        connection = getattr(self._local, 'connection', None)
        if connection is None:
            connection_type = (
                http.client.HTTPSConnection
                if self.scheme == 'https'
                else http.client.HTTPConnection
            )
            connection = connection_type(self.host, self.port, timeout=self.timeout)
            self._local.connection = connection
        return connection

    def _path(self, path: str) -> str:
        return f'{self.root_path}/{path.lstrip("/")}'

    def request(self, method: str, path: str, body: bytes | None = None) -> RequestResult:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'trimly-benchmark/1.0',
        }
        if body is not None:
            headers['Content-Type'] = 'application/json'

        started = time.perf_counter()
        try:
            connection = self._connection()
            connection.request(method, self._path(path), body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
            elapsed = time.perf_counter() - started
            return RequestResult(response.status, elapsed, response_body)
        except Exception as exc:
            elapsed = time.perf_counter() - started
            connection = getattr(self._local, 'connection', None)
            if connection is not None:
                connection.close()
                del self._local.connection
            return RequestResult(None, elapsed, error=f'{type(exc).__name__}: {exc}')


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError('Value must be at least 1.')
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError('Value must not be negative.')
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError('Value must be greater than 0.')
    return parsed


def percentile(sorted_values: list[float], percentage: float) -> float:
    index = max(0, math.ceil(percentage * len(sorted_values)) - 1)
    return sorted_values[index]


def run_benchmark(
    name: str,
    request: Callable[[int], RequestResult],
    expected_status: int,
    request_count: int,
    concurrency: int,
    warmup_count: int,
) -> bool:
    worker_count = min(concurrency, request_count)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        if warmup_count:
            list(executor.map(request, range(-warmup_count, 0)))

        started = time.perf_counter()
        results = list(executor.map(request, range(request_count)))
        wall_seconds = time.perf_counter() - started

    statuses = Counter(result.status for result in results if result.status is not None)
    errors = Counter(result.error for result in results if result.error is not None)
    successful = sum(result.status == expected_status for result in results)
    latencies_ms = sorted(result.elapsed_seconds * 1000 for result in results)

    print(f'\n{name}')
    print(f'  Requests:    {request_count}')
    print(f'  Concurrency: {worker_count}')
    print(f'  Successful:  {successful}/{request_count}')
    print(f'  Throughput:  {request_count / wall_seconds:.2f} requests/second')
    print(f'  Statuses:    {dict(sorted(statuses.items()))}')
    if errors:
        print(f'  Errors:      {dict(errors)}')
    print('  Latency:')
    print(f'    average: {statistics.fmean(latencies_ms):.2f} ms')
    print(f'    p50:     {percentile(latencies_ms, 0.50):.2f} ms')
    print(f'    p95:     {percentile(latencies_ms, 0.95):.2f} ms')
    print(f'    p99:     {percentile(latencies_ms, 0.99):.2f} ms')
    print(f'    maximum: {latencies_ms[-1]:.2f} ms')

    if statuses[429]:
        print(f'\n{RATE_LIMIT_GUIDANCE}', file=sys.stderr)

    return successful == request_count


def create_short_code(client: BenchmarkClient, target_url: str) -> str:
    body = json.dumps({'url': target_url}).encode()
    result = client.request('POST', '/api/shorten', body)
    if result.error:
        raise RuntimeError(f'Could not create benchmark link: {result.error}')
    if result.status != 201:
        raise RuntimeError(
            f'Could not create benchmark link: HTTP {result.status}, '
            f'{result.body.decode(errors="replace")}'
        )

    response_body = json.loads(result.body)
    code = response_body.get('code')
    if not isinstance(code, str):
        raise RuntimeError('Shorten response did not contain a string code.')
    return code


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Benchmark a running Trimly service using only the Python standard library.',
        epilog=(
            'Examples:\n'
            '  python scripts/benchmark.py\n'
            '  python scripts/benchmark.py --operation both --requests 5000 --concurrency 50\n'
            '  python scripts/benchmark.py --code aB3xZ --requests 10000'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument(
        '--operation',
        choices=('redirect', 'shorten', 'both'),
        default='redirect',
    )
    parser.add_argument('--requests', type=positive_int, default=1000)
    parser.add_argument('--concurrency', type=positive_int, default=20)
    parser.add_argument('--warmup', type=non_negative_int, default=20)
    parser.add_argument('--timeout', type=positive_float, default=5.0)
    parser.add_argument(
        '--target-url',
        default='https://example.com/trimly-benchmark',
        help='Long URL used by shorten requests and redirect setup.',
    )
    parser.add_argument(
        '--code',
        help='Existing code to use for redirect tests. Skips creation of a setup link.',
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        client = BenchmarkClient(args.base_url, args.timeout)
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2

    succeeded = True

    code = args.code
    if args.operation in {'redirect', 'both'} and code is None:
        try:
            code = create_short_code(client, args.target_url)
        except (RuntimeError, json.JSONDecodeError) as exc:
            print(f'error: {exc}', file=sys.stderr)
            if 'HTTP 429' in str(exc):
                print(f'\n{RATE_LIMIT_GUIDANCE}', file=sys.stderr)
            return 1

    if args.operation in {'shorten', 'both'}:
        payload = json.dumps({'url': args.target_url}).encode()
        succeeded &= run_benchmark(
            'Shorten benchmark',
            lambda _: client.request('POST', '/api/shorten', payload),
            expected_status=201,
            request_count=args.requests,
            concurrency=args.concurrency,
            warmup_count=args.warmup,
        )

    if args.operation in {'redirect', 'both'}:
        assert code is not None
        succeeded &= run_benchmark(
            'Redirect benchmark',
            lambda _: client.request('GET', f'/{quote(code, safe="")}'),
            expected_status=302,
            request_count=args.requests,
            concurrency=args.concurrency,
            warmup_count=args.warmup,
        )

    if not succeeded:
        print('\nSome requests failed. Check the status and error counts above.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
