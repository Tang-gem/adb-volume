#include <windows.h>
#include <stdlib.h>
#include <string.h>

#define ID_BTN_UP     1
#define ID_BTN_DOWN   2
#define ADB_PATH      "D:\\scrcpy-win64-v3.3.4\\adb.exe"
#define CMD_UP        "shell input keyevent 24"
#define CMD_DOWN      "shell input keyevent 25"
#define LIMIT_INTERVAL 30

DWORD g_last_adb_call_time = 0;

void run_adb_command(int up) {
    DWORD current_time = GetTickCount();
    if (current_time - g_last_adb_call_time < LIMIT_INTERVAL) {
        return;
    }
    g_last_adb_call_time = current_time;

    STARTUPINFO si = {0};
    PROCESS_INFORMATION pi = {0};
    char cmdLine[MAX_PATH] = {0};
    strncpy(cmdLine, ADB_PATH, MAX_PATH - 1);
    strncat(cmdLine, " ", MAX_PATH - strlen(cmdLine) - 1);
    strncat(cmdLine, up ? CMD_UP : CMD_DOWN, MAX_PATH - strlen(cmdLine) - 1);

    si.cb = sizeof(STARTUPINFO);
    si.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
    si.wShowWindow = SW_HIDE;

    HANDLE hNull = CreateFile("NUL", GENERIC_WRITE, FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (hNull == INVALID_HANDLE_VALUE) {
        return;
    }
    si.hStdError = hNull;
    si.hStdOutput = hNull;

    BOOL bRet = CreateProcess(
        NULL,
        cmdLine,
        NULL,
        NULL,
        TRUE,
        CREATE_NO_WINDOW | HIGH_PRIORITY_CLASS,
        NULL,
        NULL,
        &si,
        &pi
    );

    if (bRet) {
        if (pi.hProcess) CloseHandle(pi.hProcess);
        if (pi.hThread) CloseHandle(pi.hThread);
    }
    if (hNull != INVALID_HANDLE_VALUE) CloseHandle(hNull);
}

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    switch(msg) {
        case WM_COMMAND: {
            UINT id = LOWORD(wParam);
            if (id == ID_BTN_UP) {
                run_adb_command(1);
            } else if (id == ID_BTN_DOWN) {
                run_adb_command(0);
            }
            break;
        }
        case WM_PAINT: {
            PAINTSTRUCT ps;
            HDC hdc = BeginPaint(hwnd, &ps);
            RECT rc;
            GetClientRect(hwnd, &rc);
            FillRect(hdc, &rc, (HBRUSH)(COLOR_WINDOW + 1));
            EndPaint(hwnd, &ps);
            break;
        }
        case WM_DESTROY:
            PostQuitMessage(0);
            break;
        default:
            return DefWindowProc(hwnd, msg, wParam, lParam);
    }
    return 0;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    WNDCLASS wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = "AdbVolumeCtrl";
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);

    if (!RegisterClass(&wc)) {
        MessageBox(NULL, "窗口类注册失败！", "错误", MB_ICONERROR | MB_OK);
        return 1;
    }

    // 窗口尺寸
    int win_w = 250;
    int win_h = 120;

    // 获取屏幕尺寸（包含任务栏）
    int screen_w = GetSystemMetrics(SM_CXSCREEN);
    int screen_h = GetSystemMetrics(SM_CYSCREEN);
    
    // 计算右下角坐标：屏幕宽度-窗口宽度，屏幕高度-窗口高度
    // 额外减20是为了避开任务栏，避免窗口被遮挡
    int x = screen_w - win_w - 300;
    int y = screen_h - win_h - 50;

    HWND hwnd = CreateWindowEx(
        0,
        "AdbVolumeCtrl",
        "ADB Volume Controller",
        WS_OVERLAPPEDWINDOW & ~(WS_THICKFRAME | WS_MAXIMIZEBOX),
        x, y, win_w, win_h, // 使用右下角坐标
        NULL, NULL, hInstance, NULL
    );

    if (!hwnd) {
        MessageBox(NULL, "窗口创建失败！", "错误", MB_ICONERROR | MB_OK);
        return 1;
    }

    CreateWindow("BUTTON", "Volume +",
        WS_TABSTOP | WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
        30, 30, 80, 40,
        hwnd, (HMENU)ID_BTN_UP, hInstance, NULL);

    CreateWindow("BUTTON", "Volume -",
        WS_TABSTOP | WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
        130, 30, 80, 40,
        hwnd, (HMENU)ID_BTN_DOWN, hInstance, NULL);

    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }
    return (int)msg.wParam;
}