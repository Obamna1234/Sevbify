#ifndef PyBridge_h
#define PyBridge_h

/// Starts the embedded Python (once). `resource_path` is the app bundle's resource folder (it holds "python",
/// "app" and "app_packages"). Returns 0 when Python is ready, otherwise a short message is put in `error`.
int sev_py_start(const char *resource_path, char *error, int error_len);

/// Calls ios_entry.call(name, args_json) and returns its JSON text ({"ok": ..., "value"/"error": ...}).
/// Safe from any thread. The caller frees the result with free().
char *sev_py_call(const char *name, const char *args_json);

#endif
