import contextlib
import io
from unittest import mock

from django.test import SimpleTestCase

from scripts import benchmark


class BenchmarkTests(SimpleTestCase):
    def test_rate_limited_results_print_actionable_guidance(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            succeeded = benchmark.run_benchmark(
                'Shorten benchmark',
                lambda _: benchmark.RequestResult(status=429, elapsed_seconds=0.001),
                expected_status=201,
                request_count=1,
                concurrency=1,
                warmup_count=0,
            )

        self.assertFalse(succeeded)
        self.assertIn('TRIMLY_WRITE_RATE=10000/min', stderr.getvalue())
        self.assertIn('--force-recreate web', stderr.getvalue())

    @mock.patch('scripts.benchmark.BenchmarkClient')
    @mock.patch('scripts.benchmark.create_short_code')
    @mock.patch('scripts.benchmark.run_benchmark')
    def test_both_operation_creates_redirect_fixture_before_load(
        self,
        run_benchmark,
        create_short_code,
        benchmark_client,
    ):
        events = []
        benchmark_client.return_value = mock.sentinel.client
        create_short_code.side_effect = lambda client, url: events.append('fixture') or 'aB3xZ'
        run_benchmark.side_effect = lambda name, *args, **kwargs: events.append(name) or True

        result = benchmark.main(
            ['--operation', 'both', '--requests', '1', '--concurrency', '1', '--warmup', '0']
        )

        self.assertEqual(result, 0)
        self.assertEqual(events, ['fixture', 'Shorten benchmark', 'Redirect benchmark'])

    @mock.patch('scripts.benchmark.BenchmarkClient')
    @mock.patch(
        'scripts.benchmark.create_short_code',
        side_effect=RuntimeError('Could not create benchmark link: HTTP 429, throttled'),
    )
    def test_rate_limited_fixture_prints_guidance(
        self,
        create_short_code,
        benchmark_client,
    ):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            result = benchmark.main(['--operation', 'redirect'])

        self.assertEqual(result, 1)
        self.assertIn('TRIMLY_WRITE_RATE=10000/min', stderr.getvalue())
