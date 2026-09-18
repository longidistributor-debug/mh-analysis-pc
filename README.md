# MH Analysis PC

Windows desktop version of MH Analysis.

## Current release

**v80.0 Native WebView2 Portable**

- Native Windows host window
- WebView2 control rendered inside the EXE window
- FCS candle/history analysis backend
- Independent timeframe analysis
- TradingView visual chart
- API key and WhatsApp settings stored locally on the PC
- Analysis-only application; no broker execution or automated trading

## Project structure

- `main.go` — Windows host, local HTTP API, FCS data access, settings and native WebView2 host
- `web/` — embedded desktop UI and analysis engine
- `rsrc_windows_amd64.syso` — Windows icon/resource object
- `.github/workflows/build-windows.yml` — builds the Windows x64 EXE and publishes it to `dist/`
- `dist/` — generated portable EXE

## Build

Requires Go 1.23.2+.

```powershell
go build -ldflags="-H=windowsgui" -o "dist/MH Analysis Desktop v80.0 Native WebView2 Portable.exe" .
```

The application uses the Microsoft WebView2 Runtime available on supported Windows systems.

> No FCS API key is committed to this repository. The key is entered by the user and stored locally at runtime.
