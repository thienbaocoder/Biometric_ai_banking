// // ======= Configs dễ chỉnh khi demo (đã nới lỏng) =======
// const CFG = {
//   overlayRatio: 0.58,   // khung oval
//   roiPadding: 0.06,     // bo viền để loại nền rìa

//   dwellMs: 1200,        // cần giữ ổn định liên tục 1.2s
//   poseTimeoutMs: 9000,  // 9s/pose mới tính fail
//   motionMax: 9.5,       // cho phép chuyển động lớn hơn
//   sharpMin: 18,         // bớt khắt khe độ nét

//   checkIntervalMs: 80   // đo mỗi 80ms
// };

// let stream = null;
// const cam = document.getElementById("cam");
// const overlay = document.getElementById("overlay");
// const ctxOv = overlay.getContext("2d");
// const out = document.getElementById("out");
// const poseHint = document.getElementById("poseHint");
// const kMotion = document.getElementById("kMotion");
// const kSharp  = document.getElementById("kSharp");
// const kStable = document.getElementById("kStable");
// const progressFill = document.getElementById("progressFill");
// const userIdShow = document.getElementById("userIdShow");
// let userId = null;

// // ROI từ khung oval (theo pixel canvas)
// let ROI = { cx: 320, cy: 240, rw: 200, rh: 230 };

// function show(x){ out.textContent = JSON.stringify(x, null, 2); }
// const sleep = (ms)=>new Promise(r=>setTimeout(r,ms));

// // -------- Overlay (oval) + tính ROI --------
// function drawOverlay(ratio = CFG.overlayRatio){
//   const w = overlay.width, h = overlay.height;
//   ctxOv.clearRect(0,0,w,h);

//   ctxOv.fillStyle = "rgba(0,0,0,.15)";
//   ctxOv.fillRect(0,0,w,h);
//   ctxOv.save();
//   ctxOv.globalCompositeOperation = "destination-out";

//   const cx = w/2, cy = h/2;
//   const rw = Math.min(w*0.55, h*0.65) * ratio;
//   const rh = rw * 1.10;

//   ctxOv.beginPath();
//   ctxOv.ellipse(cx,cy,rw,rh,0,0,Math.PI*2);
//   ctxOv.fill();
//   ctxOv.restore();

//   ctxOv.strokeStyle = "rgba(255,255,255,.9)";
//   ctxOv.lineWidth = 3;
//   ctxOv.beginPath(); ctxOv.ellipse(cx,cy,rw,rh,0,0,Math.PI*2); ctxOv.stroke();

//   ctxOv.strokeStyle = "rgba(255,255,255,.35)";
//   ctxOv.lineWidth = 1;
//   ctxOv.beginPath(); ctxOv.moveTo(cx,cy-10); ctxOv.lineTo(cx,cy+10); ctxOv.stroke();
//   ctxOv.beginPath(); ctxOv.moveTo(cx-10,cy); ctxOv.lineTo(cx+10,cy); ctxOv.stroke();

//   const padX = rw * CFG.roiPadding;
//   const padY = rh * CFG.roiPadding;
//   ROI = { cx, cy, rw: rw - padX, rh: rh - padY };
// }

// async function startCam(){
//   if (stream) return;
//   stream = await navigator.mediaDevices.getUserMedia({
//     video: { width: 960, height: 720, facingMode: "user" }, // độ phân giải cao hơn
//     audio: false
//   });
//   cam.srcObject = stream;
//   await cam.play();
//   drawOverlay(CFG.overlayRatio);
// }
// document.getElementById("btnCam").onclick = startCam;

// // ------ Capture + crop ROI ------
// function captureCanvas(){
//   const c = document.createElement("canvas");
//   // dùng đúng kích thước stream cho nét
//   const track = stream?.getVideoTracks?.()[0];
//   const settings = track ? track.getSettings() : {};
//   c.width  = settings.width  || 960;
//   c.height = settings.height || 720;
//   const g = c.getContext("2d", { willReadFrequently: true });
//   g.imageSmoothingEnabled = false;
//   g.drawImage(cam,0,0,c.width,c.height);
//   return c;
// }

// function cropCanvasToRoi(srcCanvas){
//   const w = srcCanvas.width, h = srcCanvas.height;
//   const { cx, cy, rw, rh } = ROI;

//   const x = Math.max(0, Math.floor(cx/w * w - rw/w * w));
//   const y = Math.max(0, Math.floor(cy/h * h - rh/h * h));

//   // vì ROI tính theo canvas 640x480 trước đây => scale theo tỉ lệ
//   const scaleX = w / 640, scaleY = h / 480;
//   const cw = Math.min(w - x, Math.floor((rw*2) * scaleX));
//   const ch = Math.min(h - y, Math.floor((rh*2) * scaleY));

//   const out = document.createElement("canvas");
//   out.width = cw; out.height = ch;
//   out.getContext("2d").drawImage(srcCanvas, x, y, cw, ch, 0, 0, cw, ch);
//   return out;
// }

// function toBase64FromRoi(cnv){
//   const roi = cropCanvasToRoi(cnv);
//   return roi.toDataURL("image/jpeg", 0.95).split(",")[1];
// }

// // ---------- Metrics (motion/sharpness) + smoothing ----------
// let lastFrameGray = null;
// let emaMotion = null, emaSharp = null;
// const EMA_ALPHA = 0.35;

// function frameMetrics(){
//   const c = captureCanvas();
//   const g = c.getContext("2d");
//   const img = g.getImageData(0,0,c.width,c.height);
//   const data = img.data, w = img.width, h = img.height;

//   // gray
//   const gray = new Uint8Array(w*h);
//   for (let i=0, j=0;i<data.length;i+=4,++j){
//     gray[j] = (data[i]*0.299 + data[i+1]*0.587 + data[i+2]*0.114) | 0;
//   }

//   // motion = MAD
//   let motion = 0;
//   if (lastFrameGray && lastFrameGray.length === gray.length){
//     let sum = 0, n = gray.length;
//     for (let i=0;i<n;i++) sum += Math.abs(gray[i]-lastFrameGray[i]);
//     motion = sum / n;
//   }
//   lastFrameGray = gray;

//   // sharpness = variance of Laplacian
//   let lapSum=0, lapSq=0, cnt=0;
//   for (let y=1;y<h-1;y++){
//     for (let x=1;x<w-1;x++){
//       const i = y*w + x;
//       const v = 4*gray[i] - gray[i-1] - gray[i+1] - gray[i-w] - gray[i+w];
//       lapSum += v; lapSq += v*v; cnt++;
//     }
//   }
//   const mean = lapSum / Math.max(1,cnt);
//   let sharpness = Math.max(0, (lapSq/Math.max(1,cnt)) - mean*mean);

//   // EMA smoothing
//   emaMotion = (emaMotion==null) ? motion : (EMA_ALPHA*motion + (1-EMA_ALPHA)*emaMotion);
//   emaSharp  = (emaSharp==null)  ? sharpness : (EMA_ALPHA*sharpness + (1-EMA_ALPHA)*emaSharp);

//   return { motion: emaMotion, sharpness: emaSharp, canvas: c };
// }

// function setPoseText(pose, remainMs=null){
//   const base = pose==="front" ? "Nhìn thẳng"
//             : pose==="left"  ? "Quay sang trái"
//                               : "Quay sang phải";
//   poseHint.textContent = remainMs==null ? base : `${base} • còn ${(remainMs/1000).toFixed(1)}s`;
// }
// function setProgress(p){ progressFill.style.width = `${Math.max(0, Math.min(1,p))*100}%`; }

// // --------- Auto-capture với hysteresis (không reset ngay) ----------
// async function autoSnapOnePose(pose){
//   const deadline = performance.now() + CFG.poseTimeoutMs;
//   let stableScore = 0; // 0 → 1
//   let lastCanvas = null;

//   while (true){
//     const now = performance.now();
//     const remain = Math.max(0, deadline - now);

//     const m = frameMetrics();
//     lastCanvas = m.canvas;

//     kMotion.textContent = (m.motion ?? 0).toFixed(1);
//     kSharp.textContent  = (m.sharpness ?? 0).toFixed(0);

//     const isStable = (m.motion <= CFG.motionMax) && (m.sharpness >= CFG.sharpMin);

//     // tăng/giảm điểm ổn định mượt mà (hysteresis)
//     if (isStable) stableScore = Math.min(1, stableScore + CFG.checkIntervalMs/CFG.dwellMs);
//     else          stableScore = Math.max(0, stableScore - 0.5 * CFG.checkIntervalMs/CFG.dwellMs);

//     kStable.textContent = isStable ? "OK" : "…";
//     kStable.className   = isStable ? "ok" : "warn";

//     const pStab = stableScore;
//     const pTime = 1 - (remain / CFG.poseTimeoutMs);
//     setPoseText(pose, remain);
//     setProgress(Math.max(pStab, pTime*0.7));

//     if (stableScore >= 1){
//       setProgress(1);
//       return { ok:true, canvas: m.canvas };
//     }

//     if (remain <= 0){
//       kStable.textContent = "TIMEOUT";
//       kStable.className = "bad";
//       return { ok:false, canvas: lastCanvas };
//     }
//     await sleep(CFG.checkIntervalMs);
//   }
// }

// async function post(url, body){
//   const r = await fetch(url, {
//     method: "POST",
//     headers: { "Content-Type":"application/json" },
//     body: JSON.stringify(body)
//   });
//   const t = await r.text();
//   try { return JSON.parse(t); } catch { return t; }
// }

// // ------------- ENROLL -------------
// document.getElementById("btnEnroll").onclick = async () => {
//   await startCam();
//   const order = ["front","left","right"];
//   const images = {};
//   for (const p of order){
//     const res = await autoSnapOnePose(p);
//     images[p] = toBase64FromRoi(res.canvas); // chỉ gửi ROI
//     await sleep(200);
//   }
//   poseHint.textContent = "Đang gửi ảnh đăng ký…"; setProgress(0);
//   const r = await post("/auth/register", { images });
//   show(r);
//   if (r.userId){ userId = r.userId; userIdShow.textContent = String(userId); }
//   poseHint.textContent = "Đăng ký xong.";
//   setProgress(1);
// };

// // ------------- VERIFY -------------
// document.getElementById("btnVerify").onclick = async () => {
//   if (!userId){ alert("Chưa có UserId. Vui lòng Enroll trước."); return; }
//   await startCam();

//   const purpose = document.querySelector('input[name="purpose"]:checked').value;
//   const start = await post("/auth/verify/start", { userId, purpose });
//   if (!start.sequence){ show(start); return; }

//   const frames = [];
//   for (const p of start.sequence){
//     const res = await autoSnapOnePose(p);
//     frames.push({ pose: p, imageBase64: toBase64FromRoi(res.canvas) });
//     await sleep(150);
//   }
//   poseHint.textContent = "Đang gửi ảnh xác thực…"; setProgress(0);

//   const r = await post("/auth/verify/submit", { challengeId: start.challengeId, frames });
//   show(r);

//   if (r && r.token){
//     poseHint.textContent = "Xác thực thành công";
//     kStable.textContent = "ALLOW"; kStable.className = "ok";
//   } else if (r && r.stepUp === "OTP_REQUIRED"){
//     poseHint.textContent = "Yêu cầu OTP bổ sung";
//     kStable.textContent = "STEP_UP"; kStable.className = "warn";
//   } else {
//     poseHint.textContent = "Xác thực thất bại";
//     kStable.textContent = "FAIL"; kStable.className = "bad";
//   }
//   setProgress(1);
// };


// // Add
// // Hiệu ứng đổi màu nền khi đăng ký hoặc xác thực
// function startProcessing() {
//   document.body.classList.add("processing");
// }

// function stopProcessing() {
//   document.body.classList.remove("processing");
// }

// // Giả lập tiến trình xác thực
// document.getElementById("btnEnroll")?.addEventListener("click", () => {
//   startProcessing();
//   setTimeout(stopProcessing, 6000);
// });

// document.getElementById("btnVerify")?.addEventListener("click", () => {
//   startProcessing();
//   setTimeout(stopProcessing, 5000);
// });

// ======= Configs dễ chỉnh khi demo (đã nới lỏng) =======
const CFG = {
  overlayRatio: 0.58,   // khung oval
  roiPadding: 0.06,     // bo viền để loại nền rìa

  dwellMs: 1200,        // cần giữ ổn định liên tục 1.2s
  poseTimeoutMs: 9000,  // 9s/pose mới tính fail
  motionMax: 9.5,       // cho phép chuyển động lớn hơn
  sharpMin: 18,         // bớt khắt khe độ nét

  checkIntervalMs: 80   // đo mỗi 80ms
};

// ---------- Helper: lấy phần tử an toàn ----------
const $ = (id) => document.getElementById(id) || null;

// Chỉ tham chiếu nếu DOM có phần tử tương ứng
let stream = null;
const cam        = $("cam");
const overlay    = $("overlay");
const ctxOv      = overlay ? overlay.getContext("2d") : null;
const out        = $("out");
const poseHint   = $("poseHint");
const kMotion    = $("kMotion");
const kSharp     = $("kSharp");
const kStable    = $("kStable");
const progressFill = $("progressFill");
const userIdShow = $("userIdShow");

// ====== Persist userId qua các trang / F5 ======
const USER_KEY = "bio_userId";
let userId = null;

function loadUserId() {
  const saved = localStorage.getItem(USER_KEY);
  if (saved) {
    userId = saved;
    if (userIdShow) userIdShow.textContent = String(saved);
  }
}
function saveUserId(id) {
  userId = id;
  localStorage.setItem(USER_KEY, String(id));
  if (userIdShow) userIdShow.textContent = String(id);
}
loadUserId(); // khôi phục ngay khi script load

// ROI từ khung oval (theo pixel canvas “chuẩn” 640x480)
let ROI = { cx: 320, cy: 240, rw: 200, rh: 230 };

function show(x){
  if (out) out.textContent = typeof x === "string" ? x : JSON.stringify(x, null, 2);
}
const sleep = (ms)=>new Promise(r=>setTimeout(r,ms));

// -------- Overlay (oval) + tính ROI --------
function drawOverlay(ratio = CFG.overlayRatio){
  if (!overlay || !ctxOv) return;

  const w = overlay.width, h = overlay.height;
  ctxOv.clearRect(0,0,w,h);

  ctxOv.fillStyle = "rgba(0,0,0,.15)";
  ctxOv.fillRect(0,0,w,h);
  ctxOv.save();
  ctxOv.globalCompositeOperation = "destination-out";

  const cx = w/2, cy = h/2;
  const rw = Math.min(w*0.55, h*0.65) * ratio;
  const rh = rw * 1.10;

  ctxOv.beginPath();
  ctxOv.ellipse(cx,cy,rw,rh,0,0,Math.PI*2);
  ctxOv.fill();
  ctxOv.restore();

  ctxOv.strokeStyle = "rgba(255,255,255,.9)";
  ctxOv.lineWidth = 3;
  ctxOv.beginPath(); ctxOv.ellipse(cx,cy,rw,rh,0,0,Math.PI*2); ctxOv.stroke();

  ctxOv.strokeStyle = "rgba(255,255,255,.35)";
  ctxOv.lineWidth = 1;
  ctxOv.beginPath(); ctxOv.moveTo(cx,cy-10); ctxOv.lineTo(cx,cy+10); ctxOv.stroke();
  ctxOv.beginPath(); ctxOv.moveTo(cx-10,cy); ctxOv.lineTo(cx+10,cy); ctxOv.stroke();

  const padX = rw * CFG.roiPadding;
  const padY = rh * CFG.roiPadding;
  ROI = { cx, cy, rw: rw - padX, rh: rh - padY };
}

async function startCam(){
  if (!cam) { alert("Không tìm thấy camera element trên trang này."); return; }
  if (stream) return;
  stream = await navigator.mediaDevices.getUserMedia({
    video: { width: 960, height: 720, facingMode: "user" },
    audio: false
  });
  cam.srcObject = stream;
  await cam.play();
  drawOverlay(CFG.overlayRatio);
}

// ------ Capture + crop ROI ------
function captureCanvas(){
  if (!cam) return null;
  const c = document.createElement("canvas");

  const track = cam.srcObject?.getVideoTracks?.()[0];
  const settings = track ? track.getSettings() : {};
  c.width  = settings.width  || 960;
  c.height = settings.height || 720;
  const g = c.getContext("2d", { willReadFrequently: true });
  g.imageSmoothingEnabled = false;
  g.drawImage(cam,0,0,c.width,c.height);
  return c;
}

function cropCanvasToRoi(srcCanvas){
  if (!srcCanvas) return null;

  const w = srcCanvas.width, h = srcCanvas.height;
  const { cx, cy, rw, rh } = ROI;

  // ROI gốc định nghĩa theo 640x480 → scale sang kích thước thật
  const scaleX = w / 640, scaleY = h / 480;
  const cw = Math.min(w, Math.floor((rw*2) * scaleX));
  const ch = Math.min(h, Math.floor((rh*2) * scaleY));

  const x = Math.max(0, Math.floor(w/2 - cw/2));
  const y = Math.max(0, Math.floor(h/2 - ch/2));

  const out = document.createElement("canvas");
  out.width = cw; out.height = ch;
  out.getContext("2d").drawImage(srcCanvas, x, y, cw, ch, 0, 0, cw, ch);
  return out;
}

function toBase64FromRoi(cnv){
  const roi = cropCanvasToRoi(cnv);
  if (!roi) return null;
  return roi.toDataURL("image/jpeg", 0.95).split(",")[1];
}

// ---------- Metrics (motion/sharpness) + smoothing ----------
let lastFrameGray = null;
let emaMotion = null, emaSharp = null;
const EMA_ALPHA = 0.35;

function frameMetrics(){
  const c = captureCanvas();
  if (!c) return { motion: 0, sharpness: 0, canvas: null };
  const g = c.getContext("2d");
  const img = g.getImageData(0,0,c.width,c.height);
  const data = img.data, w = img.width, h = img.height;

  // gray
  const gray = new Uint8Array(w*h);
  for (let i=0, j=0;i<data.length;i+=4,++j){
    gray[j] = (data[i]*0.299 + data[i+1]*0.587 + data[i+2]*0.114) | 0;
  }

  // motion = MAD
  let motion = 0;
  if (lastFrameGray && lastFrameGray.length === gray.length){
    let sum = 0, n = gray.length;
    for (let i=0;i<n;i++) sum += Math.abs(gray[i]-lastFrameGray[i]);
    motion = sum / n;
  }
  lastFrameGray = gray;

  // sharpness = variance of Laplacian
  let lapSum=0, lapSq=0, cnt=0;
  for (let y=1;y<h-1;y++){
    for (let x=1;x<w-1;x++){
      const i = y*w + x;
      const v = 4*gray[i] - gray[i-1] - gray[i+1] - gray[i-w] - gray[i+w];
      lapSum += v; lapSq += v*v; cnt++;
    }
  }
  const mean = lapSum / Math.max(1,cnt);
  let sharpness = Math.max(0, (lapSq/Math.max(1,cnt)) - mean*mean);

  // EMA smoothing
  emaMotion = (emaMotion==null) ? motion : (EMA_ALPHA*motion + (1-EMA_ALPHA)*emaMotion);
  emaSharp  = (emaSharp==null)  ? sharpness : (EMA_ALPHA*sharpness + (1-EMA_ALPHA)*emaSharp);

  return { motion: emaMotion, sharpness: emaSharp, canvas: c };
}

function setPoseText(pose, remainMs=null){
  if (!poseHint) return;
  const base = pose==="front" ? "Nhìn thẳng"
            : pose==="left"  ? "Quay sang trái"
                              : "Quay sang phải";
  poseHint.textContent = remainMs==null ? base : `${base} • còn ${(remainMs/1000).toFixed(1)}s`;
}
function setProgress(p){
  if (progressFill) progressFill.style.width = `${Math.max(0, Math.min(1,p))*100}%`;
}

// --------- Auto-capture với hysteresis ----------
async function autoSnapOnePose(pose){
  const deadline = performance.now() + CFG.poseTimeoutMs;
  let stableScore = 0; // 0 → 1
  let lastCanvas = null;

  while (true){
    const now = performance.now();
    const remain = Math.max(0, deadline - now);

    const m = frameMetrics();
    lastCanvas = m.canvas;

    if (kMotion) kMotion.textContent = (m.motion ?? 0).toFixed(1);
    if (kSharp)  kSharp.textContent  = (m.sharpness ?? 0).toFixed(0);

    const isStable = (m.motion <= CFG.motionMax) && (m.sharpness >= CFG.sharpMin);

    // tăng/giảm điểm ổn định mượt mà (hysteresis)
    if (isStable) stableScore = Math.min(1, stableScore + CFG.checkIntervalMs/CFG.dwellMs);
    else          stableScore = Math.max(0, stableScore - 0.5 * CFG.checkIntervalMs/CFG.dwellMs);

    if (kStable){
      kStable.textContent = isStable ? "OK" : "…";
      kStable.className   = isStable ? "ok" : "warn";
    }

    const pStab = stableScore;
    const pTime = 1 - (remain / CFG.poseTimeoutMs);
    setPoseText(pose, remain);
    setProgress(Math.max(pStab, pTime*0.7));

    if (stableScore >= 1){
      setProgress(1);
      return { ok:true, canvas: m.canvas };
    }

    if (remain <= 0){
      if (kStable){ kStable.textContent = "TIMEOUT"; kStable.className = "bad"; }
      return { ok:false, canvas: lastCanvas };
    }
    await sleep(CFG.checkIntervalMs);
  }
}

async function post(url, body){
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(body)
  });
  const t = await r.text();
  try { return JSON.parse(t); } catch { return t; }
}

// ------------- ENROLL -------------
$("btnEnroll")?.addEventListener("click", async () => {
  await startCam();
  const order = ["front","left","right"];
  const images = {};
  for (const p of order){
    const res = await autoSnapOnePose(p);
    const b64 = toBase64FromRoi(res.canvas);
    if (!b64){ alert("Không lấy được khung hình. Vui lòng thử lại."); return; }
    images[p] = b64; // chỉ gửi ROI
    await sleep(200);
  }
  if (poseHint) { poseHint.textContent = "Đang gửi ảnh đăng ký…"; setProgress(0); }
  const r = await post("/auth/register", { images });
  show(r);
  if (r && r.userId){
    saveUserId(r.userId); // <<<<<< PERSIST ID
  }
  if (poseHint) { poseHint.textContent = "Đăng ký xong."; setProgress(1); }
});

// ------------- VERIFY -------------
$("btnVerify")?.addEventListener("click", async () => {
  if (!userId){
    loadUserId();
    if (!userId){
      alert("Chưa có UserId. Vui lòng Enroll trước.");
      return;
    }
  }
  await startCam();

  const purpose = document.querySelector('input[name="purpose"]:checked')?.value || "LOGIN";
  const start = await post("/auth/verify/start", { userId, purpose });
  if (!start || !start.sequence){ show(start || "Lỗi: không nhận được chuỗi pose."); return; }

  const frames = [];
  for (const p of start.sequence){
    const res = await autoSnapOnePose(p);
    const b64 = toBase64FromRoi(res.canvas);
    if (!b64){ alert("Không lấy được khung hình. Vui lòng thử lại."); return; }
    frames.push({ pose: p, imageBase64: b64 });
    await sleep(150);
  }
  if (poseHint) { poseHint.textContent = "Đang gửi ảnh xác thực…"; setProgress(0); }

  const r = await post("/auth/verify/submit", { challengeId: start.challengeId, frames });
  show(r);

  if (r && r.token){
    if (poseHint) poseHint.textContent = "Xác thực thành công";
    if (kStable){ kStable.textContent = "ALLOW"; kStable.className = "ok"; }
  } else if (r && r.stepUp === "OTP_REQUIRED"){
    if (poseHint) poseHint.textContent = "Yêu cầu OTP bổ sung";
    if (kStable){ kStable.textContent = "STEP_UP"; kStable.className = "warn"; }
  } else {
    if (poseHint) poseHint.textContent = "Xác thực thất bại";
    if (kStable){ kStable.textContent = "FAIL"; kStable.className = "bad"; }
  }
  setProgress(1);
});

// ------------- Bật camera -------------
$("btnCam")?.addEventListener("click", startCam);

// ---------- Hiệu ứng đổi màu nền khi đang xử lý ----------
function startProcessing(){ document.body.classList.add("processing"); }
function stopProcessing(){ document.body.classList.remove("processing"); }

// Giả lập tiến trình xác thực/đăng ký cho hiệu ứng nền
$("btnEnroll")?.addEventListener("click", () => {
  startProcessing(); setTimeout(stopProcessing, 6000);
});
$("btnVerify")?.addEventListener("click", () => {
  startProcessing(); setTimeout(stopProcessing, 5000);
});
