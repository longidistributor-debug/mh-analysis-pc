//go:build windows

package main

import (
 "encoding/json"
 "net/http"
 "net/http/httptest"
 "os"
 "path/filepath"
 "strings"
 "testing"
)

func TestV27RecordsAndEABridgeShareSignalID(t *testing.T) {
 t.Setenv("APPDATA", t.TempDir())
 t.Setenv("LOCALAPPDATA", t.TempDir())
 mux:=http.NewServeMux()
 registerRecordsV2Routes(mux)
 registerEASignalBridgeRoutes(mux)
 post:=func(path,body string) map[string]any {
  t.Helper(); w:=httptest.NewRecorder()
  mux.ServeHTTP(w,httptest.NewRequest("POST",path,strings.NewReader(body)))
  if w.Code!=200 { t.Fatalf("%s: %d %s",path,w.Code,w.Body.String()) }
  var out map[string]any
  if err:=json.Unmarshal(w.Body.Bytes(),&out);err!=nil {t.Fatal(err)}
  return out
 }
 capture:=`{"signal_id":"MH-test-27","symbol":"XAUUSD","timeframe":"15m","direction":"BUY","entry":2490,"sl":2480,"tp1":2510,"tp2":2520,"action":"NEW"}`
 if got:=post("/api/records-v2/capture",capture);got["saved"]!=true {t.Fatal(got)}
 if got:=post("/api/records-v2/capture",capture);got["duplicate"]!=true {t.Fatal(got)}
 post("/api/mt5/ea/send",`{"signal_id":"MH-test-27","symbol":"XAUUSD","type":"BUY","entry":2490,"sl":2480,"tp":2510,"lot":0.02}`)
 dir,err:=mt5CommonBridgeDir();if err!=nil {t.Fatal(err)}
 b,err:=os.ReadFile(filepath.Join(dir,"signal.txt"));if err!=nil {t.Fatal(err)}
 if !strings.HasPrefix(string(b),"MH-test-27|XAUUSD|BUY|") {t.Fatal(string(b))}
 w:=httptest.NewRecorder();mux.ServeHTTP(w,httptest.NewRequest("GET","/api/records-v2",nil))
 if !strings.Contains(w.Body.String(),"MH-test-27") {t.Fatal(w.Body.String())}
}
