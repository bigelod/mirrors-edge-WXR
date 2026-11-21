// mevr-launcher - start Mirror's Edge with the mod's engine config already in place.
//
// Why this exists: the engine reads TdEngine.ini during its own startup, before any of our code
// runs, and then writes its in-memory copy back over the file. Anything the mod writes from
// DllMain is therefore both too late for THIS run and erased before the next one - which is why
// a config change has always needed a second launch. A launcher runs before the engine, so it can
// make the file correct and have that same run see it.
//
// It does exactly what the mod's own config install does, and nothing else:
//   1. copy mevr-TdEngine.ini (the bundled profile) over the game's TdEngine.ini if they differ
//   2. set ResX/ResY from mevr.ini's Resolution, so the engine and the forced display mode agree
//   3. start MirrorsEdge.exe and wait for it
//
// No window on success; a MessageBox only if it cannot start the game. Everything it does goes to
// mevr-launcher.log beside itself, because on the headset there is no console to read.
//
// Later: this is where the auto-update belongs (fetch version.txt, compare, replace d3d9.dll and
// mevr.ini, then launch). The launch path below is already the full sequence around it.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>
#include <vector>
#include <string>
#include <cstdio>
#include <cstdarg>

static wchar_t g_dir[MAX_PATH] = L"";
static std::string g_log;

static void Log(const char* fmt, ...)
{
    char line[1024];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    SYSTEMTIME st;
    GetLocalTime(&st);
    char stamp[32];
    _snprintf_s(stamp, sizeof(stamp), _TRUNCATE, "%02d:%02d:%02d ", st.wHour, st.wMinute, st.wSecond);
    g_log += stamp;
    g_log += line;
    g_log += "\r\n";
    OutputDebugStringA(line);
}

static void FlushLog()
{
    if (!g_dir[0] || g_log.empty()) return;
    wchar_t path[MAX_PATH];
    _snwprintf_s(path, _TRUNCATE, L"%s\\mevr-launcher.log", g_dir);
    HANDLE h = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD wrote = 0;
    WriteFile(h, g_log.data(), (DWORD)g_log.size(), &wrote, nullptr);
    CloseHandle(h);
}

static bool ReadAll(const wchar_t* path, std::string& out)
{
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(h, &size) || size.QuadPart < 0 || size.QuadPart > 4 * 1024 * 1024) {
        CloseHandle(h);
        return false;
    }
    out.assign((size_t)size.QuadPart, '\0');
    DWORD got = 0;
    const bool ok = out.empty() ||
        (ReadFile(h, &out[0], (DWORD)out.size(), &got, nullptr) && got == out.size());
    CloseHandle(h);
    return ok;
}

static bool ReadResolution(unsigned* w, unsigned* h);   // defined below the desktop probe

static bool WriteAll(const wchar_t* path, const std::string& data)
{
    const DWORD attrs = GetFileAttributesW(path);
    if (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_READONLY))
        SetFileAttributesW(path, attrs & ~FILE_ATTRIBUTE_READONLY);

    wchar_t temp[MAX_PATH];
    _snwprintf_s(temp, _TRUNCATE, L"%s.tmp", path);
    HANDLE h = CreateFileW(temp, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD wrote = 0;
    const bool ok = data.empty() ||
        (WriteFile(h, data.data(), (DWORD)data.size(), &wrote, nullptr) && wrote == data.size());
    CloseHandle(h);
    if (!ok) { DeleteFileW(temp); return false; }
    if (!MoveFileExW(temp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temp);
        return false;
    }
    return true;
}

// The engine's config lives in the redirected Documents folder, which on this machine is under
// OneDrive. SHGetFolderPath follows the redirection; the fallbacks cover a bare Wine prefix where
// the shell call fails.
static bool FindEngineConfig(wchar_t* out)
{
    static const wchar_t* const kTail =
        L"\\EA Games\\Mirror's Edge\\TdGame\\Config\\TdEngine.ini";
    wchar_t docs[MAX_PATH] = L"";
    if (FAILED(SHGetFolderPathW(nullptr, CSIDL_PERSONAL, nullptr, 0, docs)) || !docs[0]) {
        wchar_t home[MAX_PATH];
        if (GetEnvironmentVariableW(L"USERPROFILE", home, MAX_PATH)) {
            _snwprintf_s(docs, MAX_PATH, _TRUNCATE, L"%s\\Documents", home);
        }
    }
    if (!docs[0]) return false;
    _snwprintf_s(out, MAX_PATH, _TRUNCATE, L"%s%s", docs, kTail);
    return true;
}

// The container's screen. WinlatorXR runs the game on a virtual display sized by the container,
// so the current display mode IS the size to render at. EnumDisplaySettings is asked first
// because it reports the real mode; GetSystemMetrics is the fallback for a bare Wine desktop
// where the mode call fails. SCREEN_WIDTH/SCREEN_HEIGHT are honoured when present because some
// container builds export them and they are authoritative there.
static bool DetectDesktop(unsigned* w, unsigned* h)
{
    wchar_t buf[32];
    DWORD n = GetEnvironmentVariableW(L"SCREEN_WIDTH", buf, 32);
    unsigned ew = 0, eh = 0;
    if (n > 0 && n < 32) {
        wchar_t buf2[32];
        DWORD n2 = GetEnvironmentVariableW(L"SCREEN_HEIGHT", buf2, 32);
        if (n2 > 0 && n2 < 32) {
            ew = (unsigned)_wtoi(buf);
            eh = (unsigned)_wtoi(buf2);
            if (ew >= 640 && eh >= 360 && ew <= 8192 && eh <= 8192) {
                *w = ew; *h = eh;
                Log("desktop from SCREEN_WIDTH/HEIGHT: %ux%u", ew, eh);
                return true;
            }
        }
    }
    DEVMODEW dm{};
    dm.dmSize = sizeof(dm);
    if (EnumDisplaySettingsW(nullptr, ENUM_CURRENT_SETTINGS, &dm) &&
        dm.dmPelsWidth >= 640 && dm.dmPelsHeight >= 360) {
        *w = dm.dmPelsWidth;
        *h = dm.dmPelsHeight;
        Log("desktop from the current display mode: %ux%u", *w, *h);
        return true;
    }
    const int sw = GetSystemMetrics(SM_CXSCREEN);
    const int sh = GetSystemMetrics(SM_CYSCREEN);
    if (sw >= 640 && sh >= 360) {
        *w = (unsigned)sw;
        *h = (unsigned)sh;
        Log("desktop from GetSystemMetrics: %ux%u", *w, *h);
        return true;
    }
    Log("could not read the desktop size");
    return false;
}

// Rewrite the single `Resolution = ...` line in mevr.ini, leaving every other byte alone.
// Returns false when the file did not change.
static bool SetIniResolution(const wchar_t* path, unsigned w, unsigned h)
{
    std::string text;
    if (!ReadAll(path, text)) return false;
    std::string out;
    out.reserve(text.size() + 16);
    bool changed = false, seen = false;
    size_t at = 0;
    while (at < text.size()) {
        size_t e = text.find('\n', at);
        if (e == std::string::npos) e = text.size();
        size_t contentEnd = e;
        if (contentEnd > at && text[contentEnd - 1] == '\r') --contentEnd;
        const std::string line = text.substr(at, contentEnd - at);
        size_t s = line.find_first_not_of(" \t");
        if (!seen && s != std::string::npos && line.compare(s, 10, "Resolution") == 0) {
            const size_t eq = line.find('=', s);
            if (eq != std::string::npos) {
                char repl[64];
                _snprintf_s(repl, sizeof(repl), _TRUNCATE, "Resolution = %ux%u", w, h);
                out += repl;
                seen = true;
                changed = true;
                out.append(text, contentEnd, e - contentEnd);
                if (e < text.size()) out += '\n';
                at = e + 1;
                continue;
            }
        }
        out.append(text, at, e - at);
        if (e < text.size()) out += '\n';
        at = e + 1;
    }
    if (!changed) { Log("mevr.ini has no Resolution line - left alone"); return false; }
    if (!WriteAll(path, out)) { Log("mevr.ini write FAILED (error %lu)", GetLastError()); return false; }
    return true;
}

// Make mevr.ini and the engine agree with the container's screen before anything starts.
static void ApplyContainerResolution()
{
    unsigned w = 0, h = 0;
    if (!DetectDesktop(&w, &h)) return;

    wchar_t ini[MAX_PATH];
    _snwprintf_s(ini, _TRUNCATE, L"%s\\mevr.ini", g_dir);
    unsigned oldW = 0, oldH = 0;
    const bool had = ReadResolution(&oldW, &oldH);
    if (had && oldW == w && oldH == h) {
        Log("mevr.ini Resolution already %ux%u", w, h);
        return;
    }
    if (SetIniResolution(ini, w, h)) {
        if (had) Log("mevr.ini Resolution %ux%u -> %ux%u (the container desktop wins)", oldW, oldH, w, h);
        else     Log("mevr.ini Resolution = %ux%u (from the container desktop)", w, h);
    }

    // The engine renders 16:9 and letterboxes the rest; say so rather than let it surprise.
    const int lhs = (int)(w * 9), rhs = (int)(h * 16);
    const int diff = lhs > rhs ? lhs - rhs : rhs - lhs;
    if (diff > 16 * 8)
        Log("warning: %ux%u is not 16:9 (%.2f) - the engine will letterbox", w, h,
            h ? (double)w / (double)h : 0.0);
}

// Resolution = 1920x1080 (or auto). Auto follows the container desktop, which is what the launcher
// cannot know better than the engine, so auto leaves ResX/ResY alone.
static bool ReadResolution(unsigned* w, unsigned* h)
{
    wchar_t ini[MAX_PATH];
    _snwprintf_s(ini, _TRUNCATE, L"%s\\mevr.ini", g_dir);
    std::string text;
    if (!ReadAll(ini, text)) return false;
    size_t at = 0;
    while (at < text.size()) {
        size_t e = text.find('\n', at);
        if (e == std::string::npos) e = text.size();
        std::string line = text.substr(at, e - at);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        size_t s = line.find_first_not_of(" \t");
        if (s != std::string::npos) line.erase(0, s);
        if (line.compare(0, 10, "Resolution") == 0) {
            size_t eq = line.find('=');
            if (eq != std::string::npos) {
                std::string v = line.substr(eq + 1);
                size_t f = v.find_first_not_of(" \t");
                if (f != std::string::npos) v.erase(0, f);
                unsigned a = 0, b = 0;
                if (sscanf_s(v.c_str(), "%ux%u", &a, &b) == 2 && a >= 320 && b >= 240) {
                    *w = a; *h = b;
                    return true;
                }
            }
        }
        at = e + 1;
    }
    return false;
}

// Rewrite ResX= / ResY= in place, preserving every other byte including CRLF.
static std::string SetResolution(const std::string& in, unsigned w, unsigned h)
{
    std::string out;
    out.reserve(in.size() + 32);
    size_t at = 0;
    while (at < in.size()) {
        size_t e = in.find('\n', at);
        if (e == std::string::npos) e = in.size();
        size_t contentEnd = e;
        if (contentEnd > at && in[contentEnd - 1] == '\r') --contentEnd;
        const std::string line = in.substr(at, contentEnd - at);
        if (line.compare(0, 5, "ResX=") == 0 || line.compare(0, 5, "ResY=") == 0) {
            char repl[32];
            _snprintf_s(repl, sizeof(repl), _TRUNCATE, "%s=%u",
                        line[3] == 'X' ? "ResX" : "ResY", line[3] == 'X' ? w : h);
            out += repl;
            out.append(in, contentEnd, e - contentEnd);
        } else {
            out.append(in, at, e - at);
        }
        // The terminator is written explicitly: `at` jumps past it, and forgetting it here
        // concatenated every line of the config into its predecessor.
        if (e < in.size()) out += '\n';
        at = e + 1;
    }
    return out;
}

static bool ApplyConfig()
{
    wchar_t bundled[MAX_PATH];
    _snwprintf_s(bundled, _TRUNCATE, L"%s\\mevr-TdEngine.ini", g_dir);
    wchar_t target[MAX_PATH];
    if (!FindEngineConfig(target)) { Log("no Documents folder found - config left alone"); return false; }

    std::string wanted, current;
    if (!ReadAll(bundled, wanted)) {
        Log("mevr-TdEngine.ini not beside the launcher - config left alone");
    } else {
        unsigned rw = 0, rh = 0;
        if (ReadResolution(&rw, &rh)) {
            wanted = SetResolution(wanted, rw, rh);
            Log("resolution from mevr.ini: %ux%u", rw, rh);
        } else {
            Log("mevr.ini Resolution is auto or absent - ResX/ResY left as bundled");
        }
        const bool same = ReadAll(target, current) &&
                          current.size() == wanted.size() &&
                          memcmp(current.data(), wanted.data(), wanted.size()) == 0;
        if (same) {
            Log("TdEngine.ini already matches (%zu bytes)", wanted.size());
        } else {
            wchar_t backup[MAX_PATH];
            _snwprintf_s(backup, _TRUNCATE, L"%s.mevr-backup", target);
            if (GetFileAttributesW(backup) == INVALID_FILE_ATTRIBUTES &&
                GetFileAttributesW(target) != INVALID_FILE_ATTRIBUTES)
                CopyFileW(target, backup, TRUE);
            if (WriteAll(target, wanted))
                Log("TdEngine.ini updated (%zu bytes) -> %S", wanted.size(), target);
            else
                Log("TdEngine.ini write FAILED (error %lu) -> %S", GetLastError(), target);
        }
    }
    return true;
}

// ---- backup of the version this launcher shipped with ----
//
// The launcher is the updater and never updates itself, so the files beside it at first run are
// the set it "came with". Keeping a copy lets a player roll back without a fresh download, which
// matters because a bad update is otherwise unrecoverable on a headset with no file manager worth
// using.
//
// Written ONCE per version and never overwritten: if the folder already holds a d3d9.dll, the
// backup is complete and untouched. A later launcher with a new version creates its own folder, so
// upgrading does not destroy the version you might want to return to.
static std::string TrimVersion(std::string v)
{
    while (!v.empty() && (v.back() == '\r' || v.back() == '\n' || v.back() == ' ' || v.back() == '\t'))
        v.pop_back();
    size_t s = v.find_first_not_of(" \t");
    if (s == std::string::npos) return std::string();
    v.erase(0, s);
    for (char& c : v)
        if (!(isalnum((unsigned char)c) || c == '.' || c == '-' || c == '_')) c = '_';
    return v;
}

static void BackupBundledVersion()
{
    wchar_t verPath[MAX_PATH];
    _snwprintf_s(verPath, _TRUNCATE, L"%s\\version.txt", g_dir);
    std::string version;
    if (!ReadAll(verPath, version)) version.clear();
    version = TrimVersion(version);
    if (version.empty()) version = "unversioned";

    wchar_t root[MAX_PATH], dir[MAX_PATH];
    _snwprintf_s(root, _TRUNCATE, L"%s\\WXRBACKUP", g_dir);
    CreateDirectoryW(root, nullptr);                 // ignored when it already exists
    wchar_t wideVer[64];
    _snwprintf_s(wideVer, _TRUNCATE, L"%S", version.c_str());
    _snwprintf_s(dir, _TRUNCATE, L"%s\\v%s", root, wideVer);
    CreateDirectoryW(dir, nullptr);
    _snwprintf_s(dir, _TRUNCATE, L"%s\\v%s", root, wideVer);

    // Already backed up? The launcher only ever writes this once per version.
    wchar_t probe[MAX_PATH];
    _snwprintf_s(probe, _TRUNCATE, L"%s\\d3d9.dll", dir);
    if (GetFileAttributesW(probe) != INVALID_FILE_ATTRIBUTES) {
        Log("backup: WXRBACKUP\\v%s already holds this version - left untouched", version.c_str());
        return;
    }

    static const wchar_t* const kFiles[] = { L"d3d9.dll", L"mevr.ini", L"mevr-TdEngine.ini",
                                             L"version.txt", L"notes.txt" };
    int copied = 0;
    for (const wchar_t* name : kFiles) {
        wchar_t from[MAX_PATH], to[MAX_PATH];
        _snwprintf_s(from, _TRUNCATE, L"%s\\%s", g_dir, name);
        _snwprintf_s(to, _TRUNCATE, L"%s\\%s", dir, name);
        if (GetFileAttributesW(from) == INVALID_FILE_ATTRIBUTES) continue;
        if (CopyFileW(from, to, TRUE)) {
            ++copied;
        } else {
            Log("backup: could not copy %S (error %lu)", name, GetLastError());
        }
    }
    if (copied) {
        Log("backup: WXRBACKUP\\v%s created with %d file(s)", version.c_str(), copied);
        wchar_t note[MAX_PATH];
        _snwprintf_s(note, _TRUNCATE, L"%s\\RESTORE.txt", dir);
        std::string text =
            "This is the mod version this launcher shipped with, kept so a bad update can be\r\n"
            "undone without downloading anything again.\r\n\r\n"
            "To roll back: close the game, copy every file in this folder back into\r\n"
            "..\\..\\  (the game's Binaries folder), answering Yes to replace, and start the game\r\n"
            "through mevr-launcher.exe as usual. version.txt is included so the launcher's update\r\n"
            "check sees the older version and offers the upgrade again.\r\n\r\n"
            "Nothing in this folder is used while the game runs. The launcher writes it once and\r\n"
            "never changes it, so it is safe to keep.\r\n";
        WriteAll(note, text);
    } else {
        Log("backup: nothing to back up beside the launcher");
    }
}

static bool FindGame(wchar_t* out)
{
    static const wchar_t* const kRel[] = { L"%s\\MirrorsEdge.exe", L"%s\\..\\MirrorsEdge.exe",
                                           L"%s\\..\\..\\Binaries\\MirrorsEdge.exe" };
    for (const wchar_t* rel : kRel) {
        wchar_t path[MAX_PATH];
        _snwprintf_s(path, _TRUNCATE, rel, g_dir);
        if (GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
            wchar_t full[MAX_PATH];
            if (GetFullPathNameW(path, MAX_PATH, full, nullptr)) {
                wcscpy_s(out, MAX_PATH, full);
                return true;
            }
        }
    }
    return false;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, LPWSTR, int)
{
    GetModuleFileNameW(nullptr, g_dir, MAX_PATH);
    if (wchar_t* slash = wcsrchr(g_dir, L'\\')) *slash = 0;

    Log("mevr-launcher starting from %S", g_dir);

    wchar_t game[MAX_PATH];
    if (!FindGame(game)) {
        Log("MirrorsEdge.exe not found beside the launcher or up two folders");
        FlushLog();
        MessageBoxW(nullptr, L"MirrorsEdge.exe was not found next to mevr-launcher.exe.\n"
                              L"Put the launcher in the game's Binaries folder.",
                    L"Mirror's Edge VR", MB_ICONERROR | MB_OK);
        return 2;
    }

    ApplyContainerResolution();
    ApplyConfig();
    BackupBundledVersion();
    FlushLog();        // the log must exist DURING the run, not only after the game exits

    // Working directory is the exe's folder: the engine resolves its packages relative to it.
    wchar_t work[MAX_PATH];
    wcscpy_s(work, MAX_PATH, game);
    if (wchar_t* slash = wcsrchr(work, L'\\')) *slash = 0;

    std::wstring cmd = L"\"";
    cmd += game;
    cmd += L"\"";
    std::wstring args = GetCommandLineW();
    // Anything after our own exe name is passed through untouched (WinlatorXR may add flags).
    if (!args.empty() && args[0] == L'"') {
        size_t close = args.find(L'"', 1);
        if (close != std::wstring::npos && close + 1 < args.size())
            cmd += args.substr(close + 1);
    }

    STARTUPINFOW si{};
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    std::vector<wchar_t> mutableCmd(cmd.begin(), cmd.end());
    mutableCmd.push_back(0);

    Log("starting %S", cmd.c_str());
    if (!CreateProcessW(game, mutableCmd.data(), nullptr, nullptr, FALSE, 0, nullptr, work,
                        &si, &pi)) {
        Log("CreateProcessW FAILED (error %lu)", GetLastError());
        FlushLog();
        MessageBoxW(nullptr, L"Mirror's Edge could not be started.\nSee mevr-launcher.log.",
                    L"Mirror's Edge VR", MB_ICONERROR | MB_OK);
        return 3;
    }

    Log("pid %lu, waiting for exit", pi.dwProcessId);
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 0;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    Log("game exited with %lu", code);

    ApplyConfig();     // the engine rewrites its config on the way out; put ours back
    FlushLog();
    return (int)code;
}
