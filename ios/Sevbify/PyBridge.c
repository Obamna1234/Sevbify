// Runs Sevbify's shared Python code (the same core/ the Windows and Android apps use) inside the iPhone app.
// Set up as Python's iOS guide describes: isolated config, UTF-8 mode, no bytecode writing (the app is signed),
// PYTHONHOME = <bundle>/python, and app + app_packages on the path.
#include <Python/Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "PyBridge.h"

static int started = 0;
static PyObject *entry_call = NULL;

static void set_error(char *error, int len, const char *msg) {
    if (error && len > 0) snprintf(error, len, "%s", msg ? msg : "unknown error");
}

static int add_site_dir(PyObject *site, const char *path) {
    PyObject *fn = PyObject_GetAttrString(site, "addsitedir");
    if (!fn) return -1;
    PyObject *arg = PyUnicode_FromString(path);
    PyObject *res = PyObject_CallOneArg(fn, arg);
    Py_XDECREF(arg); Py_XDECREF(fn);
    if (!res) return -1;
    Py_DECREF(res);
    return 0;
}

int sev_py_start(const char *resource_path, char *error, int error_len) {
    if (started) return 0;
    PyStatus status;
    PyPreConfig preconfig;
    PyConfig config;
    char path[4096];

    setenv("NO_COLOR", "1", 1);
    PyPreConfig_InitIsolatedConfig(&preconfig);
    PyConfig_InitIsolatedConfig(&config);
    preconfig.utf8_mode = 1;
    config.buffered_stdio = 0;
    config.write_bytecode = 0;
    config.install_signal_handlers = 1;

    status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) { set_error(error, error_len, status.err_msg); PyConfig_Clear(&config); return 1; }

    snprintf(path, sizeof(path), "%s/python", resource_path);
    wchar_t *home = Py_DecodeLocale(path, NULL);
    status = PyConfig_SetString(&config, &config.home, home);
    PyMem_RawFree(home);
    if (PyStatus_Exception(status)) { set_error(error, error_len, status.err_msg); PyConfig_Clear(&config); return 2; }

    status = PyConfig_Read(&config);
    if (PyStatus_Exception(status)) { set_error(error, error_len, status.err_msg); PyConfig_Clear(&config); return 3; }

    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) { set_error(error, error_len, status.err_msg); return 4; }

    PyObject *site = PyImport_ImportModule("site");
    if (!site) { PyErr_Print(); set_error(error, error_len, "can't import site"); return 5; }
    snprintf(path, sizeof(path), "%s/app_packages", resource_path);
    if (add_site_dir(site, path) != 0) { PyErr_Print(); Py_DECREF(site); set_error(error, error_len, "app_packages"); return 6; }
    snprintf(path, sizeof(path), "%s/app", resource_path);
    if (add_site_dir(site, path) != 0) { PyErr_Print(); Py_DECREF(site); set_error(error, error_len, "app"); return 7; }
    Py_DECREF(site);

    PyObject *entry = PyImport_ImportModule("ios_entry");
    if (!entry) { PyErr_Print(); set_error(error, error_len, "can't import ios_entry (see the log)"); return 8; }
    entry_call = PyObject_GetAttrString(entry, "call");
    Py_DECREF(entry);
    if (!entry_call) { PyErr_Print(); set_error(error, error_len, "ios_entry.call is missing"); return 9; }

    started = 1;
    PyEval_SaveThread();          // let other threads take the interpreter (each call takes the GIL)
    return 0;
}

char *sev_py_call(const char *name, const char *args_json) {
    if (!started) return strdup("{\"ok\": false, \"error\": \"Python isn't running\"}");
    PyGILState_STATE gil = PyGILState_Ensure();
    char *out = NULL;
    PyObject *res = PyObject_CallFunction(entry_call, "ss", name, args_json ? args_json : "[]");
    if (res && PyUnicode_Check(res)) {
        const char *text = PyUnicode_AsUTF8(res);
        out = strdup(text ? text : "");
    } else {
        PyErr_Print();
        out = strdup("{\"ok\": false, \"error\": \"Python call failed\"}");
    }
    Py_XDECREF(res);
    PyGILState_Release(gil);
    return out;
}
