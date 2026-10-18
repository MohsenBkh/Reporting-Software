#-----------------------------------------------------------------------------
# ReportForge - PyInstaller runtime hook (runs before ANY user code).
#
# Purpose: prevent the frozen application from crashing at startup with
#
#     AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
#
# Chain (ReportForge v1.1.1 and older):
#     reportforge.py -> app.main -> app.pyside_compat -> `from six.moves import ...`
#       -> shibokensupport feature_imported -> inspect.getsource
#       -> PyInstaller's pyi_rth_inspect -> inspect.getfile
#       -> importlib._bootstrap._module_repr_from_spec
#       -> list(spec.loader._path)   # six's virtual modules have no _path
#
# The failing line lives in CPython 3.12.0-3.12.3 (fixed in 3.12.4). This hook
# makes the failure impossible regardless of the Python patch version, by
# guarding `inspect` for file-less (virtual) modules and by giving six's
# virtual modules a real __file__.
#
# This file is intentionally self-contained (standard library only) and
# ASCII-only: it must be importable while the frozen archive is still booting.
#-----------------------------------------------------------------------------
import sys
import types


def _repr_is_vulnerable():
    """True if this interpreter's _module_repr_from_spec chokes on loaders without _path."""
    import importlib._bootstrap as _bootstrap

    class _ProbeLoader(object):
        pass

    class _ProbeSpec(object):
        name = "reportforge._probe"
        origin = None
        loader = None
        has_location = False

    _probe = _ProbeSpec()
    _probe.loader = _ProbeLoader()
    try:
        _bootstrap._module_repr_from_spec(_probe)
        return False
    except AttributeError:
        return True
    except Exception:
        return False


def _reportforge_guards():
    try:
        # --- 1) make inspect safe for virtual modules -----------------------
        import inspect

        if not getattr(inspect, "_reportforge_guarded", False):
            _orig_getfile = inspect.getfile
            _orig_getsource = inspect.getsource
            _orig_getsourcefile = inspect.getsourcefile

            def _safe_getfile(obj):
                if isinstance(obj, types.ModuleType) and not getattr(obj, "__file__", None):
                    # build the error message without repr(module): repr() of a
                    # loader without _path raises on CPython 3.12.0-3.12.3
                    raise TypeError(
                        "module %s has no source file (virtual module)"
                        % (getattr(obj, "__name__", "?") or "?",))
                return _orig_getfile(obj)

            def _safe_getsource(obj):
                # six's virtual modules: shiboken asks for their source while they
                # are being imported; "no source" must never raise.
                if isinstance(obj, types.ModuleType):
                    _nm = getattr(obj, "__name__", "") or ""
                    if _nm == "six" or _nm.startswith("six."):
                        return ""
                    if not getattr(obj, "__file__", None):
                        return ""
                try:
                    return _orig_getsource(obj)
                except (OSError, TypeError, AttributeError):
                    # frozen/bundled modules have no readable source on disk
                    return ""

            def _safe_getsourcefile(obj):
                if isinstance(obj, types.ModuleType):
                    _nm = getattr(obj, "__name__", "") or ""
                    if _nm == "six" or _nm.startswith("six."):
                        return None
                try:
                    return _orig_getsourcefile(obj)
                except Exception:
                    return None

            inspect.getfile = _safe_getfile
            inspect.getsource = _safe_getsource
            inspect.getsourcefile = _safe_getsourcefile
            inspect._reportforge_guarded = True

        # --- 2) six's virtual modules get a real __file__ -------------------
        import six  # noqa: F401
        import six.moves  # noqa: F401
        from six.moves import _thread, range  # noqa: F401

        if sys.platform == "win32":
            from six.moves import winreg  # noqa: F401

        _six_file = getattr(six, "__file__", "") or ""

        # NOTE: on CPython 3.12.0-3.12.3, repr() of a file-less module raises
        # AttributeError("..._SixMetaPathImporter' object has no attribute '_path'").
        # We therefore neutralize the repr path unconditionally: every virtual
        # six module gets a real __file__ and loses its __spec__ (so repr() falls
        # back to the __file__ branch). Version/behaviour detection is kept only
        # for diagnostics.
        try:
            sys._reportforge_repr_vulnerable = _repr_is_vulnerable()
        except Exception:
            pass

        def _stub(mod):
            # 1) give file-less six modules a real __file__ (inspect.getfile safe)
            if not isinstance(mod, types.ModuleType):
                return
            _mod_name = getattr(mod, "__name__", "") or ""
            if not (_mod_name == "six" or _mod_name.startswith("six.")):
                return  # only six's own virtual modules; never aliased real modules
            if not getattr(mod, "__file__", None):
                try:
                    mod.__file__ = _six_file
                except Exception:
                    pass
            # 2) drop the spec whose origin is None: that is the exact branch of
            #    _module_repr_from_spec that touches loader._path (see NOTE above)
            _spec = getattr(mod, "__spec__", None)
            if _spec is not None and getattr(_spec, "origin", None) is None:
                try:
                    mod.__spec__ = None
                except Exception:
                    pass

        for _name, _mod in list(sys.modules.items()):
            if _name == "six" or _name.startswith("six."):
                _stub(_mod)

        _importer_cls = getattr(six, "_SixMetaPathImporter", None)
        if _importer_cls is not None and not getattr(_importer_cls, "_reportforge_patched", False):
            # create_module/load_module run BEFORE _init_module_attrs, exec_module
            # runs AFTER it; wrap all three so the fresh spec cannot be re-attached.
            for _method_name in ("create_module", "load_module", "exec_module"):
                _orig_method = getattr(_importer_cls, _method_name, None)
                if _orig_method is None or not callable(_orig_method):
                    continue

                def _wrapped(self, *args, __orig=_orig_method, **kwargs):
                    _result = __orig(self, *args, **kwargs)
                    # exec_module(module) passes the module as an argument
                    _stub(_result)
                    for _candidate in args:
                        _stub(_candidate)
                    return _result

                setattr(_importer_cls, _method_name, _wrapped)
            _importer_cls._reportforge_patched = True

        # --- 3) neutralize shiboken's module introspection hook -------------
        for _mod_name in ("shibokensupport.feature", "shibokensupport.signature.loader"):
            _mod = sys.modules.get(_mod_name)
            if _mod is None:
                continue
            _orig = getattr(_mod, "feature_imported", None)
            if _orig is None or getattr(_orig, "_reportforge_patched", False):
                continue

            def _safe_feature_imported(module, *args, __orig=_orig, **kwargs):
                _nm = getattr(module, "__name__", "") or ""
                if _nm == "six" or _nm.startswith("six."):
                    return None
                if not getattr(module, "__file__", None):
                    return None
                return __orig(module, *args, **kwargs)

            _safe_feature_imported._reportforge_patched = True
            _mod.feature_imported = _safe_feature_imported

        for _finder in list(sys.meta_path):
            _cls = type(_finder)
            _cm = getattr(_cls, "__module__", "") or ""
            if _cm.startswith("shibokensupport") or _cm == "shiboken6.feature":
                try:
                    sys.meta_path.remove(_finder)
                except ValueError:
                    pass
    except Exception:
        # a runtime hook must never be the reason the app fails to start
        pass


_reportforge_guards()
del _reportforge_guards
