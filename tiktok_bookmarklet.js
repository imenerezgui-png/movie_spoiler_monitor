/*
 BAKMA TikTok collector — free, no proxy, no bot-detection.

 HOW IT WORKS
 You browse TikTok normally in your own logged-in browser (that's not a bot, so
 TikTok doesn't block it). This snippet reads the videos already loaded on the
 page and downloads a CSV you import into the dashboard ("Import CSV" button).

 HOW TO USE
 1. In your normal browser, go to TikTok and open a hashtag or search page, e.g.:
        https://www.tiktok.com/tag/bakma
        https://www.tiktok.com/search?q=bakma%20film
        https://www.tiktok.com/search?q=بكمة
 2. Scroll down to load as many videos as you want to capture.
 3. Press F12 -> "Console" tab. Paste the whole block below. Press Enter.
 4. A file "tiktok_bakma_<time>.csv" downloads. Import it in the dashboard.
    (The dashboard scores it and drops Turkish automatically.)

 Repeat for each hashtag/search. Optionally save it as a bookmarklet — see the
 bottom of this file.
*/

(function () {
  const rows = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="/video/"]').forEach((a) => {
    const href = (a.href || "").split("?")[0];
    const m = href.match(/@([^/]+)\/video\/(\d+)/);
    if (!m) return;
    const id = m[2];
    if (seen.has(id)) return;
    seen.add(id);
    const user = m[1];
    const img = a.querySelector("img");
    const caption = img ? (img.alt || "").trim() : "";
    rows.push({
      platform: "TikTok",
      platform_id: id,
      url: href,
      creator: user,
      published_at: "",
      title: caption.slice(0, 120),
      text: caption,
    });
  });

  if (!rows.length) {
    alert("No TikTok videos found. Scroll the hashtag/search results to load videos, then run again.");
    return;
  }

  const cols = ["platform", "platform_id", "url", "creator", "published_at", "title", "text"];
  const esc = (s) => '"' + String(s == null ? "" : s).replace(/"/g, '""') + '"';
  const csv = [cols.join(",")]
    .concat(rows.map((r) => cols.map((c) => esc(r[c])).join(",")))
    .join("\r\n");

  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "tiktok_bakma_" + Date.now() + ".csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  console.log("Exported " + rows.length + " TikTok videos to CSV.");
})();

/*
 OPTIONAL BOOKMARKLET (one-click instead of pasting each time):
 Create a new bookmark and paste this entire line as its URL, then click it
 whenever you're on a TikTok hashtag/search page:

javascript:(function(){const rows=[],seen=new Set();document.querySelectorAll('a[href*="/video/"]').forEach(a=>{const href=(a.href||'').split('?')[0];const m=href.match(/@([^/]+)\/video\/(\d+)/);if(!m)return;const id=m[2];if(seen.has(id))return;seen.add(id);const user=m[1];const img=a.querySelector('img');const caption=img?(img.alt||'').trim():'';rows.push({platform:'TikTok',platform_id:id,url:href,creator:user,published_at:'',title:caption.slice(0,120),text:caption});});if(!rows.length){alert('No TikTok videos found. Scroll the results first.');return;}const cols=['platform','platform_id','url','creator','published_at','title','text'];const esc=s=>'"'+String(s==null?'':s).replace(/"/g,'""')+'"';const csv=[cols.join(',')].concat(rows.map(r=>cols.map(c=>esc(r[c])).join(','))).join('\r\n');const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='tiktok_bakma_'+Date.now()+'.csv';document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);})();
*/
