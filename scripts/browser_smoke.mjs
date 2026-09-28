// Real Chrome smoke test with fake data only; no camera or third-party test dependency.
import { spawn, execFileSync } from "node:child_process";
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = await mkdtemp(join(tmpdir(), "event-auth-chrome-"));
const server = spawn(".venv/bin/python", ["scripts/browser_fixture.py"], {stdio:"pipe"});
let serverLog = "";
server.stderr.on("data", data => {serverLog += data;});
const chrome = spawn(process.env.CHROME_BIN || "/usr/bin/google-chrome", [
  "--headless=new", "--no-first-run", "--no-default-browser-check",
  "--disable-background-networking", "--disable-sync", "--disable-extensions",
  "--remote-debugging-port=9223", "--user-data-dir=" + profile, "about:blank"
], {stdio:"ignore"});
let socket;
async function waitFor(test, label) {
  for (let attempt=0; attempt<100; attempt++) {
    try { if (await test()) return; } catch {}
    await delay(100);
  }
  throw new Error("Timed out: " + label + "\n" + serverLog);
}
try {
  await waitFor(async()=> (await fetch("http://127.0.0.1:8765/api/health")).ok, "test server");
  await waitFor(async()=> (await fetch("http://127.0.0.1:9223/json/version")).ok, "Chrome");
  const target = await (await fetch("http://127.0.0.1:9223/json/new?http://127.0.0.1:8765", {method:"PUT"})).json();
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let sequence=0;
  const pending=new Map();
  const errors=[];
  socket.onmessage=event=>{
    const value=JSON.parse(event.data);
    if(value.method==="Runtime.exceptionThrown") errors.push(value.params.exceptionDetails.text);
    if(pending.has(value.id)) {
      const {resolve,reject}=pending.get(value.id);pending.delete(value.id);
      value.error ? reject(new Error(value.error.message)) : resolve(value.result);
    }
  };
  const send=(method,params={})=>new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));
  });
  const evaluate=async expression=>{
    const value=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});
    if(value.exceptionDetails) throw new Error(JSON.stringify(value.exceptionDetails));
    return value.result.value;
  };
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride",{width:1280,height:960,deviceScaleFactor:1,mobile:false});
  const visible=async value=>evaluate("document.body.innerText.includes(" + JSON.stringify(value) + ")");
  const waitText=value=>waitFor(()=>visible(value),value);
  const click=async label=>{
    await waitFor(()=>evaluate(`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled)`),"enabled "+label);
    return evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled).click()`);
  };
  const fill=async(label,value)=>evaluate(`(()=>{
    const label=[...document.querySelectorAll('label')].find(l=>l.firstChild.textContent.trim()===${JSON.stringify(label)});
    if(!label)throw Error('Missing label');
    const input=label.querySelector('input,select');
    const proto=input.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(input,${JSON.stringify(value)});
    input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await waitText("Sign in");
  await fill("Staff username","test_browser");await fill("PIN (6–12 digits)","123456");await click("Sign in");
  await waitText("Add member");
  await fill("Member name","Test Browser Member");await fill("Mobile (optional)","TEST-BROWSER");
  await fill("Unit / flat","TEST-UNIT");await click("Save member");
  await waitText("Test Browser Member");
  assert(await visible("ID only"));
  assert(await visible("Face registration"));
  assert(await visible("Face enrollment is experimental."));
  await click("Add or replace face"); await waitText("Consent before capture");
  assert(await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Record consent and open camera').disabled"));
  assert(await evaluate("document.querySelector('video').srcObject === null"));
  await click("Cancel face capture");
  await mkdir("docs/screenshots",{recursive:true});
  const shot=await send("Page.captureScreenshot",{format:"png"});
  await writeFile("docs/screenshots/m2-members.png",Buffer.from(shot.data,"base64"));
  await send("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),"mobile layout overflows");
  const mobileShot=await send("Page.captureScreenshot",{format:"png"});
  await writeFile("docs/screenshots/m2-members-mobile.png",Buffer.from(mobileShot.data,"base64"));
  await send("Emulation.setDeviceMetricsOverride",{width:1280,height:960,deviceScaleFactor:1,mobile:false});
  await click("Events");await waitText("Create event");await click("Create event");
  await fill("Event name","Test Browser Event");await fill("Date","2026-10-01");
  await fill("Venue","Test Browser Venue");await fill("Slot name","Test Lunch");
  await fill("Counter name","Test Counter");
  const boxes=await evaluate("document.querySelectorAll('input[type=checkbox]').length");
  for(let i=0;i<boxes;i++) await evaluate(`document.querySelectorAll('input[type=checkbox]')[${i}].click()`);
  await click("Save event");await waitText("Member choices");
  const ids=await evaluate("Array.from(document.querySelectorAll('select')).map(s=>s.options[1]?.value)");
  await fill("Member",ids[0]);await fill("Test Lunch",ids[1]);await click("Save choices");
  await waitText("Registered members: 1");
  await click("Mark event ready");await waitText("READY");
  await click("Check-in");await waitText("Choose an event");
  await waitFor(()=>evaluate("document.querySelector('select')?.options.length > 1"),"check-in events loaded");
  const eventId = await evaluate("document.querySelector('select').options[1].value");
  await fill("Event", eventId);await click("Start event check-in");await waitText("Choose a slot");
  const slotId = await evaluate("document.querySelectorAll('select')[1].options[1].value");
  await fill("Slot", slotId);await click("Search by ID, name or mobile");
  await fill("Search by ID, name or mobile", "Test Browser Member");await click("Search by ID, name or mobile");
  await waitFor(()=>evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Test Browser Member'))"),"search result");
  await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Test Browser Member')).click()");
  await click("Confirm identity & create QR PDF");await waitText("Download QR PDF");
  assert(await evaluate("document.querySelector('a.downloadPdf').href.startsWith('blob:')"));
  await send("Browser.setDownloadBehavior", {behavior:"allow", downloadPath:profile});
  await evaluate("document.querySelector('a.downloadPdf').click()");
  await waitFor(async()=> (await readdir(profile)).some(name=>name.endsWith('.pdf')), "PDF download");
  const pdfName = (await readdir(profile)).find(name=>name.endsWith('.pdf'));
  assert.equal((await readFile(join(profile,pdfName))).subarray(0,5).toString(), "%PDF-");
  const issuedShot = await send("Page.captureScreenshot",{format:"png"});
  await writeFile("docs/screenshots/m3-pdf.png",Buffer.from(issuedShot.data,"base64"));
  await click("Next member");await click("Search by ID, name or mobile");
  await click("Search by ID, name or mobile");
  await waitFor(()=>evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Test Browser Member'))"),"repeat search");
  await evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent.startsWith('Test Browser Member')).click()");
  await waitText("Coupon already issued:");
  await send("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),"check-in mobile overflow");
  await send("Emulation.setDeviceMetricsOverride",{width:1280,height:960,deviceScaleFactor:1,mobile:false});
  const qr = execFileSync(".venv/bin/python", ["-c", `import sys,subprocess,cv2
subprocess.run(['pdftoppm','-scale-to','1800','-singlefile','-png',sys.argv[1],sys.argv[2]],check=True,capture_output=True)
value,_,_=cv2.QRCodeDetector().detectAndDecode(cv2.imread(sys.argv[2]+'.png'))
assert value
print(value)`, join(profile,pdfName),join(profile,"qr-frame")], {encoding:"utf8"}).trim();
  await click("Counter");await waitText("Counter redemption");
  await waitFor(()=>evaluate("document.querySelector('select')?.options.length > 1"),"counter events");
  await fill("Event", eventId); await fill("Slot", slotId);
  const counterId = await evaluate("document.querySelectorAll('select')[2].options[1].value");
  await fill("Counter", counterId); await fill("QR payload (or USB scanner input)", qr);
  await click("Validate & redeem");
  await waitFor(()=>evaluate("document.querySelector('.counterResult.serve') !== null"),"SERVE");
  const serveShot=await send("Page.captureScreenshot",{format:"png"});
  await writeFile("docs/screenshots/m4-serve.png",Buffer.from(serveShot.data,"base64"));
  await waitFor(()=>evaluate("document.querySelector('.counterResult') === null"),"return to scanner");
  await fill("QR payload (or USB scanner input)", qr);await click("Validate & redeem");
  await waitText("ALREADY USED — DO NOT SERVE");
  await waitFor(()=>evaluate("document.querySelector('.counterResult') === null"),"return from duplicate");
  // Drop a committed duplicate response; retry must show recovered, never fresh SERVE.
  await evaluate(`window.originalFetch=window.fetch; window.dropNext=true; window.fetch=async(...args)=>{
    const response=await window.originalFetch(...args);
    if(window.dropNext && String(args[0]).endsWith('/counter/redeem')) {window.dropNext=false;throw new TypeError('Test lost response');}
    return response;
  }`);
  await fill("QR payload (or USB scanner input)", qr);await click("Validate & redeem");
  await waitText("Reconnecting — do not serve.");await click("Retry pending request safely");
  await waitText("PREVIOUS RESULT RECOVERED — DO NOT SERVE AGAIN");
  await evaluate("window.fetch=window.originalFetch");
  await waitFor(()=>evaluate("document.querySelector('.counterResult') === null"),"return from recovery");
  await click("Dashboard"); await waitText("Dashboard & coupon tools");
  await waitFor(()=>evaluate("document.querySelector('select')?.options.length > 1"),"dashboard events");
  await fill("Event", eventId);await waitText("Served: 1");
  await send("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"),"dashboard mobile overflow");
  await send("Emulation.setDeviceMetricsOverride",{width:1280,height:960,deviceScaleFactor:1,mobile:false});
  await click("Staff");await waitText("Add staff account");
  await fill("Staff username","test_volunteer");await fill("PIN (6–12 digits)","654321");
  await click("Add staff account");await waitFor(()=>evaluate("document.querySelector('input[autocomplete=off]').value===''"),"staff saved");
  await click("Sign out");await waitText("Sign in");
  await fill("Staff username","test_volunteer");await fill("PIN (6–12 digits)","654321");await click("Sign in");
  await waitText("Choose an event");
  assert.equal(await evaluate("document.querySelectorAll('nav').length"),0);
  assert.equal(errors.length,0,errors.join("\n"));
  console.log("PASS: real Chrome login, config-driven ID-only registration, event/choices/ready, M3 fallback/confirmation/PDF/duplicate block, M4 QR redemption/duplicate/recovery/dashboard, staff creation, logout and volunteer boundary.");
} catch (error) {
  console.error(error);
  throw error;
} finally {
  socket?.close();
  const exited=child=>child.exitCode!==null||child.signalCode!==null?Promise.resolve():new Promise(resolve=>child.once("exit",resolve));
  const finished=Promise.all([exited(server),exited(chrome)]);
  server.kill("SIGINT"); chrome.kill("SIGTERM");
  await finished;
  // This freshly-created temporary browser profile contains only fake test session state.
  await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
