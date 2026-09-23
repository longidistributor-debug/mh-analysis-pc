package main

import (
    "encoding/json"
    "net/http"
    "os"
    "path/filepath"
    "sort"
    "strings"
    "sync"
    "time"
)

type calendarFeedEvent struct{ Title, Country, Date, Impact, Forecast, Previous, Actual string }
type calendarUiEvent struct {
    Time string `json:"time"`; Country string `json:"country"`; Title string `json:"title"`; Impact string `json:"impact"`
    Forecast string `json:"forecast"`; Previous string `json:"previous"`; Actual string `json:"actual"`
}
type calendarUiDay struct { Date string `json:"date"`; Label string `json:"label"`; Events []calendarUiEvent `json:"events"` }
type calendarDiskV55 struct { CachedAt int64 `json:"cached_at"`; Days []calendarUiDay `json:"days"` }

var calendar3Mu sync.Mutex
var calendar3At time.Time
var calendar3Cache map[string]any
var calendar3Refreshing bool

func calendarDiskPathV55() string {
    base := os.Getenv("LOCALAPPDATA"); if base == "" { base = os.TempDir() }
    return filepath.Join(base, "MHAnalysis", "economic-calendar.json")
}

func loadCalendarDiskV55() (map[string]any, bool) {
    b, err := os.ReadFile(calendarDiskPathV55()); if err != nil { return nil, false }
    var d calendarDiskV55; if json.Unmarshal(b, &d) != nil || len(d.Days) == 0 { return nil, false }
    return map[string]any{"days": d.Days, "source": "Economic calendar • last known values", "cached_at": d.CachedAt}, true
}

func saveCalendarDiskV55(out map[string]any) {
    days, ok := out["days"].([]calendarUiDay); if !ok || len(days) == 0 { return }
    p := calendarDiskPathV55(); _ = os.MkdirAll(filepath.Dir(p), 0755)
    b, _ := json.Marshal(calendarDiskV55{CachedAt: time.Now().Unix(), Days: days})
    tmp := p + ".tmp"; if os.WriteFile(tmp, b, 0600) == nil { _ = os.Remove(p); _ = os.Rename(tmp, p) }
}

func (e *calendarFeedEvent) UnmarshalJSON(b []byte) error {
    type raw struct { Title string `json:"title"`; Country string `json:"country"`; Date string `json:"date"`; Impact string `json:"impact"`; Forecast string `json:"forecast"`; Previous string `json:"previous"`; Actual string `json:"actual"` }
    var x raw; if err := json.Unmarshal(b, &x); err != nil { return err }
    e.Title=x.Title; e.Country=x.Country; e.Date=x.Date; e.Impact=x.Impact; e.Forecast=x.Forecast; e.Previous=x.Previous; e.Actual=x.Actual
    return nil
}

func fetchCalendarFeed(cli *http.Client, endpoint string) []calendarFeedEvent {
    req, _ := http.NewRequest(http.MethodGet, endpoint, nil); req.Header.Set("User-Agent", "MH-Analysis/55")
    resp, err := cli.Do(req); if err != nil { return nil }; defer resp.Body.Close()
    if resp.StatusCode < 200 || resp.StatusCode >= 300 { return nil }
    var out []calendarFeedEvent; if json.NewDecoder(resp.Body).Decode(&out) != nil { return nil }; return out
}

func buildEconomicCalendarV55(timeout time.Duration) map[string]any {
    cli := &http.Client{Timeout: timeout}
    ch := make(chan []calendarFeedEvent, 2)
    go func(){ ch <- fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_thisweek.json") }()
    go func(){ ch <- fetchCalendarFeed(cli, "https://nfs.faireconomy.media/ff_calendar_nextweek.json") }()
    raw := make([]calendarFeedEvent,0,96)
    timer := time.NewTimer(timeout + 300*time.Millisecond); defer timer.Stop()
    for i:=0; i<2; i++ { select { case part:=<-ch: raw=append(raw,part...); case <-timer.C: i=2 } }
    type timed struct{ t time.Time; e calendarFeedEvent }
    items:=make([]timed,0,len(raw)); seen:=map[string]bool{}
    now:=time.Now(); today:=time.Date(now.Year(),now.Month(),now.Day(),0,0,0,0,now.Location())
    for _,ev:=range raw {
        impact:=strings.ToLower(strings.TrimSpace(ev.Impact)); if impact!="high"&&impact!="medium"&&impact!="med"&&impact!="low" { continue }
        t,err:=time.Parse(time.RFC3339,strings.TrimSpace(ev.Date)); if err!=nil { continue }; local:=t.Local(); if local.Before(today){continue}
        key:=local.Format(time.RFC3339)+"|"+strings.TrimSpace(ev.Country)+"|"+strings.TrimSpace(ev.Title); if seen[key]{continue}; seen[key]=true
        items=append(items,timed{t:local,e:ev})
    }
    sort.Slice(items,func(i,j int)bool{return items[i].t.Before(items[j].t)})
    selected:=make([]string,0,3); dateSeen:=map[string]bool{}
    for _,it:=range items { d:=it.t.Format("2006-01-02"); if !dateSeen[d]{dateSeen[d]=true;selected=append(selected,d);if len(selected)==3{break}} }
    days:=make([]calendarUiDay,0,len(selected))
    for _,d:=range selected {
        day:=calendarUiDay{Date:d,Events:[]calendarUiEvent{}}
        for _,it:=range items { if it.t.Format("2006-01-02")!=d{continue}; if day.Label==""{day.Label=it.t.Format("Monday, Jan 2, 2006")}; impact:=strings.TrimSpace(it.e.Impact);if strings.EqualFold(impact,"med"){impact="Medium"};day.Events=append(day.Events,calendarUiEvent{Time:it.t.Format("03:04 PM"),Country:strings.ToUpper(strings.TrimSpace(it.e.Country)),Title:strings.TrimSpace(it.e.Title),Impact:impact,Forecast:strings.TrimSpace(it.e.Forecast),Previous:strings.TrimSpace(it.e.Previous),Actual:strings.TrimSpace(it.e.Actual)}) }
        if len(day.Events)>0{days=append(days,day)}
    }
    if len(days)==0{return nil}
    return map[string]any{"days":days,"source":"Economic calendar • Low / Medium / High","cached_at":time.Now().Unix()}
}

func setCalendarCacheV55(out map[string]any) {
    if out==nil{return}; calendar3Mu.Lock(); calendar3Cache=out; calendar3At=time.Now(); calendar3Mu.Unlock(); saveCalendarDiskV55(out)
}

func refreshCalendarBackgroundV55() {
    calendar3Mu.Lock(); if calendar3Refreshing{calendar3Mu.Unlock();return}; calendar3Refreshing=true; calendar3Mu.Unlock()
    go func(){
        if out:=buildEconomicCalendarV55(3500*time.Millisecond);out!=nil{setCalendarCacheV55(out)}
        calendar3Mu.Lock();calendar3Refreshing=false;calendar3Mu.Unlock()
    }()
}

func warmStartupCalendarV55() {
    if out,ok:=loadCalendarDiskV55();ok{calendar3Mu.Lock();calendar3Cache=out;calendar3At=time.Now();calendar3Mu.Unlock();refreshCalendarBackgroundV55();return}
    if out:=buildEconomicCalendarV55(2300*time.Millisecond);out!=nil{setCalendarCacheV55(out)}
}

func economicCalendarHandler(w http.ResponseWriter,r *http.Request){
    if r.Method!=http.MethodGet{http.Error(w,"method",http.StatusMethodNotAllowed);return};w.Header().Set("Content-Type","application/json")
    calendar3Mu.Lock();cached:=calendar3Cache;age:=time.Since(calendar3At);calendar3Mu.Unlock()
    if cached!=nil{_ = json.NewEncoder(w).Encode(cached);if age>2*time.Minute{refreshCalendarBackgroundV55()};return}
    if disk,ok:=loadCalendarDiskV55();ok{calendar3Mu.Lock();calendar3Cache=disk;calendar3At=time.Now();calendar3Mu.Unlock();_ = json.NewEncoder(w).Encode(disk);refreshCalendarBackgroundV55();return}
    if out:=buildEconomicCalendarV55(3500*time.Millisecond);out!=nil{setCalendarCacheV55(out);_ = json.NewEncoder(w).Encode(out);return}
    _ = json.NewEncoder(w).Encode(map[string]any{"days":[]calendarUiDay{},"source":"Economic calendar refreshing"})
}
