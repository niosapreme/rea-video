import logging
import os
import urllib.error

import pytest

from rea_video.vlm import VLMClient, VLMConfig
from rea_video import cli
from rea_video.memory import set_pref


def config(**kw):
    return VLMConfig('https://example.test/v1', 'SECRET_KEY', ['model'], **kw)


@pytest.mark.parametrize('url', ['file:///tmp/x', 'ftp://host/x', 'not-a-url', 'https://user:pass@host/v1', 'https://host/v1?key=x', 'https://[bad'])
def test_bad_endpoint(url):
    with pytest.raises(ValueError):
        VLMClient(VLMConfig(url, 'key', ['m']))


@pytest.mark.parametrize('url', ['http://example.test/v1', 'http://192.168.1.2/v1', 'http://127.0.0.1/v1'])
def test_http_requires_explicit_loopback_exception(url):
    with pytest.raises(ValueError):
        VLMClient(VLMConfig(url, 'key', ['m']))
    if '127.0.0.1' in url:
        VLMClient(VLMConfig(url, 'key', ['m'], allow_local_http=True))


def test_budget_retry_and_redaction(tmp_path, monkeypatch, caplog):
    frame = tmp_path / 'frame.jpg'
    frame.write_bytes(b'pixels')
    calls = []
    def fail(self, model, content, max_tokens):
        calls.append(1)
        raise urllib.error.URLError('SECRET_KEY private response')
    monkeypatch.setattr(VLMClient, '_post', fail)
    monkeypatch.setattr('rea_video.vlm.time.sleep', lambda _: None)
    client = VLMClient(config(max_requests=2, max_retries=3))
    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError):
        client.ask_json('private prompt', [(frame, 'image/jpeg')])
    assert len(calls) == client.attempted == client.failed == 2
    assert 'SECRET_KEY' not in caplog.text
    assert 'private prompt' not in caplog.text


def test_timeout_failure_is_sanitized(tmp_path, monkeypatch):
    frame = tmp_path / 'frame.jpg'
    frame.write_bytes(b'pixels')
    def timeout(self, model, content, max_tokens):
        assert self.cfg.timeout == 0.5
        raise TimeoutError('SECRET_KEY')
    monkeypatch.setattr(VLMClient, '_post', timeout)
    client = VLMClient(config(timeout=0.5, max_retries=0))
    with pytest.raises(RuntimeError, match='TimeoutError') as exc:
        client.ask_json('prompt', [(frame, 'image/jpeg')])
    assert 'SECRET_KEY' not in str(exc.value)
    assert client.failed == 1


def test_success_and_size_limit(tmp_path, monkeypatch):
    frame = tmp_path / 'frame.jpg'
    frame.write_bytes(b'pixels')
    monkeypatch.setattr(VLMClient, '_post', lambda *a: '{"answer": true}')
    client = VLMClient(config(max_requests=1))
    assert client.ask_json('prompt', [(frame, 'image/jpeg')])['answer']
    assert (client.attempted, client.successful, client.failed) == (1, 1, 0)
    with pytest.raises(RuntimeError, match='budget'):
        client.ask_json('different', [(frame, 'image/jpeg')])


def test_request_size_rejected_before_network(monkeypatch):
    monkeypatch.setattr('rea_video.vlm.urllib.request.build_opener', lambda *a: pytest.fail('network called'))
    client = VLMClient(config(max_request_bytes=10, max_retries=0))
    with pytest.raises(ValueError, match='exceeds'):
        client._post('model', [{'type': 'text', 'text': 'private'}], 100)


def test_cli_consent_and_per_run_overrides(monkeypatch):
    """Repeated CLI calls in one process require fresh consent and fresh overrides."""
    set_pref('vlm', 'on')
    monkeypatch.setenv('REA_VLM_BASE_URL', 'http://127.0.0.1:12345/v1')
    monkeypatch.setenv('REA_VLM_API_KEY', 'test-key')
    monkeypatch.setenv('REA_VLM_MODEL', 'mock-model')
    monkeypatch.delenv('REA_VLM_ALLOW_LOCAL_HTTP', raising=False)
    monkeypatch.setenv('REA_VLM_MAX_REQUESTS', '7')
    transmitted = []
    runs = []

    def mocked_decompose(video, out, **kwargs):
        cfg = kwargs['vlm_config']
        runs.append((kwargs['use_vlm'], cfg))
        if kwargs['use_vlm'] and cfg is not None:
            cfg.validate()
            transmitted.append(video)
        return {'summary': {'verdict': 'local', 'shots': 0, 'confidence': 1,
                            'vlm': 'mocked', 'status': 'ok'}}

    monkeypatch.setattr('rea_video.pipeline.decompose', mocked_decompose)
    base = ['decompose', 'unused.mp4', '--no-stems']
    assert cli.main(base) == 0  # saved preference and credentials alone do not consent
    assert runs[-1] == (False, None) and not transmitted
    assert cli.main(base + ['--vlm', '--vlm-allow-local-http', '--vlm-max-requests', '2']) == 0
    assert transmitted == ['unused.mp4']
    assert runs[-1][1].allow_local_http and runs[-1][1].max_requests == 2
    assert 'REA_VLM_ALLOW_LOCAL_HTTP' not in os.environ
    assert os.environ['REA_VLM_MAX_REQUESTS'] == '7'
    assert cli.main(base) == 0
    assert runs[-1] == (False, None) and transmitted == ['unused.mp4']
    assert cli.main(base + ['--vlm']) == 2  # prior HTTP authorization did not persist
    assert runs[-1][1].allow_local_http is False
    assert runs[-1][1].max_requests == 7  # prior budget did not persist
    assert transmitted == ['unused.mp4']
