"""Download accounting without network or model dependencies."""
import sys
from types import ModuleType, SimpleNamespace

import pytest

from mythicull import config, embed


@pytest.mark.parametrize("fail", [False, True])
def test_download_counts_resume_cache_and_retries_once(tmp_path, monkeypatch, fail: bool) -> None:
    monkeypatch.setenv("MYTHICULL_DATA_DIR", str(tmp_path))
    hub = ModuleType("huggingface_hub")
    bars = ModuleType("tqdm.auto")
    class Bar:
        def __init__(self, initial: int = 0, unit: str = "B", desc: str = "file") -> None:
            self.n, self.unit, self.desc = initial, unit, desc
        def update(self, n: int = 1) -> None:
            self.n += n or 0
    bars.tqdm = Bar
    files = [SimpleNamespace(rfilename="weights", size=100), SimpleNamespace(rfilename="config", size=20)]
    hub.HfApi = lambda: SimpleNamespace(model_info=lambda *a, **kw: SimpleNamespace(sha="fixed-revision", siblings=files))
    def download(repo: str, filename: str, revision: str, local_dir, tqdm_class) -> str:
        assert revision == "fixed-revision"
        if filename == "weights":
            b = tqdm_class(initial=40)
            b.update(30)
            b.update(-20)  # A retry must not count the same bytes again.
            b.update(50)
            transfer = tqdm_class(desc="transfer")
            transfer.update(200)
            if fail:
                raise OSError("connection lost")
        return str(local_dir / filename)  # Config is cached: no bar.
    hub.hf_hub_download = download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "tqdm", ModuleType("tqdm"))
    monkeypatch.setitem(sys.modules, "tqdm.auto", bars)
    class Context:
        total = 0
        done = 0
        cancelled = False
        def set_total(self, n: int) -> None: self.total = n
        def stage(self, name: str) -> None: pass
        def advance(self, n: int) -> None:
            self.done += n
            assert self.done <= self.total
    ctx = Context()
    if fail:
        with pytest.raises(OSError): embed.download_model(ctx)
        assert not embed.model_ready()
    else:
        embed.download_model(ctx)
        assert ctx.done == ctx.total == 120
        assert embed.model_ready()
