(function(){
  if (typeof QRCodeStyling !== "function"){
    var failedPreview = document.getElementById("qr-preview");
    failedPreview.innerHTML = '<p class="generator-error" role="alert"><b>The QR generator did not load.</b><br>Refresh the page to try again. Your destination has not been uploaded.</p>';
    document.getElementById("destination-status").textContent = "Generator unavailable";
    document.querySelectorAll("#dl-png, #dl-svg, #share-btn, #embed-btn, #png-size").forEach(function(el){ el.disabled = true; });
    return;
  }
  // The demo code (shown before you type your own) points at a little celebration
  // page, so scanning your own screen opens a real, fun payoff instead of a fake URL.
  var DEMO_TEXT = "https://qrcodemadeeasy.com/scanned/";

  var state = {
    type: "link",        // "link" | "whatsapp" | "telegram" | "imessage"
    url: "",
    waCode: "1",         // country dial code (US default)
    waNumber: "",
    waMessage: "",
    tg: "",              // telegram @username or phone
    imCode: "1",         // imessage country dial code
    imNumber: "",
    imMessage: "",
    wifiSsid: "", wifiPass: "", wifiEnc: "WPA", wifiHidden: false,
    vcName: "", vcPhone: "", vcEmail: "", vcOrg: "", vcUrl: "",
    preset: "classic",
    fg: "#1b1913",
    bg: "#ffffff",
    logo: null,          // dataURL
    transparent: false
  };

  var PRESETS = {
    classic: { dots:"square",        corners:"square",       cornerDot:"square" },
    rounded: { dots:"rounded",       corners:"extra-rounded",cornerDot:"dot"    },
    dots:    { dots:"dots",          corners:"extra-rounded",cornerDot:"dot"    },
    print:   { dots:"square",        corners:"square",       cornerDot:"square" } // print-safe also forces high contrast behavior via warning
  };

  // What the code actually encodes, based on the selected type.
  function normalizedWebsite(value){
    var valueTrimmed = (value || "").trim();
    if (!valueTrimmed) return "";
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(valueTrimmed)) valueTrimmed = "https://" + valueTrimmed;
    try {
      var parsed = new URL(valueTrimmed);
      return (/^https?:$/.test(parsed.protocol) && parsed.hostname) ? parsed.href : "";
    } catch(e){ return ""; }
  }

  function currentData(){
    if (state.type === "whatsapp"){
      var digits = (state.waCode + state.waNumber).replace(/\D/g, "");
      if (digits.length < 6) return "";     // not a usable number yet, keep the demo code
      var u = "https://wa.me/" + digits;
      if (state.waMessage.trim()) u += "?text=" + encodeURIComponent(state.waMessage.trim());
      return u;
    }
    if (state.type === "telegram"){
      var v = (state.tg || "").trim().replace(/^@/, "");
      if (!v) return "";
      if (/^\+?[\d\s\-()]+$/.test(v)){                 // looks like a phone number
        var d = v.replace(/\D/g, "");
        return d.length < 6 ? "" : "https://t.me/+" + d;
      }
      var handle = v.replace(/[^A-Za-z0-9_]/g, "");    // username: letters, digits, underscore
      return handle.length < 3 ? "" : "https://t.me/" + handle;
    }
    if (state.type === "imessage"){
      var imDigits = (state.imCode + state.imNumber).replace(/\D/g, "");
      if (imDigits.length < 6) return "";
      // sms: opens Messages (iMessage on Apple-to-Apple, SMS otherwise). "?&body=" is the
      // combo that pre-fills the text on both iOS and Android parsers.
      var s = "sms:+" + imDigits;
      if (state.imMessage.trim()) s += "?&body=" + encodeURIComponent(state.imMessage.trim());
      return s;
    }
    if (state.type === "wifi"){
      var ssid = state.wifiSsid; // Spaces are part of the network name.
      if (!ssid) return "";
      // the WIFI: URI needs \ ; , : " escaped
      var esc = function(v){ return v.replace(/([\\;,:"])/g, "\\$1"); };
      var w = "WIFI:T:" + state.wifiEnc + ";S:" + esc(ssid) + ";";
      if (state.wifiEnc !== "nopass") w += "P:" + esc(state.wifiPass) + ";";
      if (state.wifiHidden) w += "H:true;";
      return w + ";";
    }
    if (state.type === "vcard"){
      var nm = state.vcName.trim();
      if (!nm && !state.vcPhone.trim() && !state.vcEmail.trim()) return "";
      // vCard text fields must escape line breaks, backslashes, commas, and semicolons.
      // This also prevents a pasted value from becoming an unintended new vCard property.
      var vEsc = function(value){ return String(value).replace(/\\/g, "\\\\").replace(/\n|\r\n?/g, "\\n").replace(/;/g, "\\;").replace(/,/g, "\\,"); };
      var v = ["BEGIN:VCARD", "VERSION:3.0"];
      if (nm){
        var nameParts = nm.split(/\s+/), family = nameParts.length > 1 ? nameParts.pop() : "", given = nameParts.join(" ");
        v.push("N:" + vEsc(family) + ";" + vEsc(given) + ";;;");
        v.push("FN:" + vEsc(nm));
      }
      if (state.vcOrg.trim()) v.push("ORG:" + vEsc(state.vcOrg.trim()));
      if (state.vcPhone.trim()) v.push("TEL;TYPE=CELL:" + vEsc(state.vcPhone.trim()));
      if (state.vcEmail.trim()) v.push("EMAIL:" + vEsc(state.vcEmail.trim()));
      if (state.vcUrl.trim()) v.push("URL:" + vEsc(state.vcUrl.trim()));
      v.push("END:VCARD");
      return v.join("\n");
    }
    return normalizedWebsite(state.url);
  }

  var PREVIEW_SIZE = 230;

  function buildOptions(size, forDownload){
    var p = PRESETS[state.preset];
    var bg = (forDownload && state.transparent) ? "rgba(0,0,0,0)" : state.bg;
    var opts = {
      width: size,
      height: size,
      type: "canvas",
      data: currentData() || DEMO_TEXT,
      image: state.logo || "", // Explicitly clear the library's previous logo.
      margin: Math.ceil(size * 4 / 29), // At least four modules, even for a 21-module symbol.
      qrOptions: {
        errorCorrectionLevel: state.logo ? "H" : (state.preset === "print" ? "Q" : "M")
      },
      dotsOptions: { color: state.fg, type: p.dots },
      cornersSquareOptions: { color: state.fg, type: p.corners },
      cornersDotOptions: { color: state.fg, type: p.cornerDot },
      backgroundOptions: { color: bg }
    };
    if (state.logo){
      opts.image = state.logo;
      opts.imageOptions = {
        crossOrigin: "anonymous",
        margin: Math.round(size * 0.02),
        imageSize: 0.28,
        hideBackgroundDots: true
      };
    }
    return opts;
  }

  var qr = new QRCodeStyling(buildOptions(PREVIEW_SIZE, false));
  var previewEl = document.getElementById("qr-preview");
  qr.append(previewEl);

  var refreshTimer;
  var lastOptions = "";
  function setExportDisabled(disabled){
    document.querySelectorAll("#dl-png, #dl-svg, #share-btn, #embed-btn").forEach(function(el){ el.disabled = disabled; });
  }
  function renderPreview(){
    clearTimeout(refreshTimer);
    try {
      var options = buildOptions(PREVIEW_SIZE, false);
      var signature = JSON.stringify(options);
      if (signature !== lastOptions){
        qr.update(options);
        lastOptions = signature;
      }
      previewEl.hidden = false;
      updateDestinationStatus();
      setExportDisabled(!currentData());
      return true;
    } catch(e){
      lastOptions = "";
      previewEl.hidden = true;
      var status = document.getElementById("destination-status");
      status.className = "destination-status error";
      status.textContent = "Too much data for this QR code. Shorten the link or contact details, or remove the logo, then try again.";
      document.getElementById("url-input").setAttribute("aria-invalid", state.type === "link" ? "true" : "false");
      setExportDisabled(true);
      return false;
    }
  }
  function refresh(){
    // Update state immediately, but encode only after a brief pause in typing.
    clearTimeout(refreshTimer);
    setExportDisabled(true);
    document.getElementById("destination-status").className = "destination-status";
    document.getElementById("destination-status").textContent = "Updating preview…";
    refreshTimer = setTimeout(renderPreview, 120);
    checkContrast();
    // any change makes a shown embed snippet stale, so collapse it until they ask again
    var eb = document.getElementById("embed-box");
    if (eb && !eb.hidden) eb.hidden = true;
    // the demo code gently breathes "scan me" until you make it your own
    var frame = document.querySelector(".qr-frame");
    if (frame) frame.classList.toggle("is-demo", !currentData());
  }

  function updateDestinationStatus(){
    var status = document.getElementById("destination-status");
    var data = currentData();
    status.className = "destination-status";
    if (!data){
      var invalidWebsite = state.type === "link" && state.url;
      status.textContent = invalidWebsite ? "Enter a valid website address." : "Demo preview — add a destination to make your code.";
      if (invalidWebsite) status.classList.add("error");
      document.getElementById("url-input").setAttribute("aria-invalid", invalidWebsite ? "true" : "false");
      return;
    }
    document.getElementById("url-input").setAttribute("aria-invalid", "false");
    status.textContent = state.type === "link" ? "Ready — opens " + data : "Ready — this preview contains your details.";
    status.classList.add("ready");
  }

  /* ---------- contrast guard ---------- */
  function luminance(hex){
    var c = hex.replace("#","");
    var r = parseInt(c.substr(0,2),16)/255, g = parseInt(c.substr(2,2),16)/255, b = parseInt(c.substr(4,2),16)/255;
    var f = function(v){ return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b);
  }
  function checkContrast(){
    var el = document.getElementById("contrast-warning");
    var lf = luminance(state.fg), lb = luminance(state.bg);
    var ratio = (Math.max(lf,lb)+0.05) / (Math.min(lf,lb)+0.05);
    var msgs = [];
    if (lf > lb){
      msgs.push("<b>Light code on a dark background:</b> many phone cameras struggle with inverted codes. Consider swapping your colors.");
    }
    if (ratio < 4){
      msgs.push("<b>Low contrast:</b> this color combination may not scan reliably, especially in print. Darken the code color or lighten the background.");
    }
    if (state.transparent){
      msgs.push("<b>Transparent background:</b> make sure you place the code on a light surface in your design, and test-scan the final layout.");
    }
    if (msgs.length){
      el.innerHTML = msgs.join("<br><br>");
      el.classList.add("show");
    } else {
      el.classList.remove("show");
    }
  }

  /* ---------- inputs ---------- */
  document.getElementById("url-input").addEventListener("input", function(e){
    state.url = e.target.value.trim();
    maybeWink(state.url);
    refresh();
  });
  document.getElementById("url-input").addEventListener("blur", function(e){
    var normalized = normalizedWebsite(state.url);
    if (normalized){
      state.url = normalized;
      e.target.value = normalized;
      renderPreview(); // Do not disable the button receiving this blur's click.
    }
  });

  /* ---------- content type: website link vs WhatsApp ---------- */
  // [ISO, name, dial code, flag]
  var COUNTRIES = [
    ["US","United States","1","🇺🇸"],["GB","United Kingdom","44","🇬🇧"],["CA","Canada","1","🇨🇦"],
    ["AU","Australia","61","🇦🇺"],["BR","Brazil","55","🇧🇷"],["MX","Mexico","52","🇲🇽"],
    ["IN","India","91","🇮🇳"],["ID","Indonesia","62","🇮🇩"],["NG","Nigeria","234","🇳🇬"],
    ["PK","Pakistan","92","🇵🇰"],["BD","Bangladesh","880","🇧🇩"],["DE","Germany","49","🇩🇪"],
    ["FR","France","33","🇫🇷"],["IT","Italy","39","🇮🇹"],["ES","Spain","34","🇪🇸"],
    ["PT","Portugal","351","🇵🇹"],["NL","Netherlands","31","🇳🇱"],["BE","Belgium","32","🇧🇪"],
    ["CH","Switzerland","41","🇨🇭"],["AT","Austria","43","🇦🇹"],["IE","Ireland","353","🇮🇪"],
    ["SE","Sweden","46","🇸🇪"],["NO","Norway","47","🇳🇴"],["DK","Denmark","45","🇩🇰"],
    ["FI","Finland","358","🇫🇮"],["PL","Poland","48","🇵🇱"],["CZ","Czech Republic","420","🇨🇿"],
    ["GR","Greece","30","🇬🇷"],["RO","Romania","40","🇷🇴"],["HU","Hungary","36","🇭🇺"],
    ["UA","Ukraine","380","🇺🇦"],["RU","Russia","7","🇷🇺"],["TR","Turkey","90","🇹🇷"],
    ["AR","Argentina","54","🇦🇷"],["CL","Chile","56","🇨🇱"],["CO","Colombia","57","🇨🇴"],
    ["PE","Peru","51","🇵🇪"],["VE","Venezuela","58","🇻🇪"],["EC","Ecuador","593","🇪🇨"],
    ["BO","Bolivia","591","🇧🇴"],["PY","Paraguay","595","🇵🇾"],["UY","Uruguay","598","🇺🇾"],
    ["GT","Guatemala","502","🇬🇹"],["CR","Costa Rica","506","🇨🇷"],["PA","Panama","507","🇵🇦"],
    ["DO","Dominican Republic","1","🇩🇴"],["CN","China","86","🇨🇳"],["JP","Japan","81","🇯🇵"],
    ["KR","South Korea","82","🇰🇷"],["PH","Philippines","63","🇵🇭"],["VN","Vietnam","84","🇻🇳"],
    ["TH","Thailand","66","🇹🇭"],["MY","Malaysia","60","🇲🇾"],["SG","Singapore","65","🇸🇬"],
    ["HK","Hong Kong","852","🇭🇰"],["TW","Taiwan","886","🇹🇼"],["AE","UAE","971","🇦🇪"],
    ["SA","Saudi Arabia","966","🇸🇦"],["IL","Israel","972","🇮🇱"],["EG","Egypt","20","🇪🇬"],
    ["ZA","South Africa","27","🇿🇦"],["KE","Kenya","254","🇰🇪"],["GH","Ghana","233","🇬🇭"],
    ["MA","Morocco","212","🇲🇦"],["NZ","New Zealand","64","🇳🇿"]
  ];
  function fillCountries(sel){
    COUNTRIES.forEach(function(c){
      var o = document.createElement("option");
      o.value = c[0]; o.setAttribute("data-dial", c[2]);
      o.textContent = c[3] + "  " + c[1] + "  (+" + c[2] + ")";
      if (c[0] === "US") o.selected = true;
      sel.appendChild(o);
    });
  }
  fillCountries(document.getElementById("wa-country"));
  fillCountries(document.getElementById("im-country"));

  var PANES = ["link","whatsapp","telegram","imessage","wifi","vcard"];
  document.querySelectorAll(".type-tab").forEach(function(tab){
    tab.addEventListener("click", function(){
      document.querySelectorAll(".type-tab").forEach(function(t){
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
        t.tabIndex = -1;
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      tab.tabIndex = 0;
      state.type = tab.dataset.type;
      PANES.forEach(function(t){ document.getElementById("pane-" + t).hidden = (state.type !== t); });
      refresh();
    });
  });
  document.getElementById("type-tabs").addEventListener("keydown", function(e){
    if (["ArrowLeft", "ArrowRight", "Home", "End"].indexOf(e.key) === -1) return;
    var tabs = Array.prototype.slice.call(document.querySelectorAll(".type-tab"));
    var at = tabs.indexOf(document.activeElement);
    if (at === -1) return;
    e.preventDefault();
    var next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (at + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[next].focus();
    tabs[next].click();
  });
  document.getElementById("wa-country").addEventListener("change", function(e){
    state.waCode = e.target.selectedOptions[0].getAttribute("data-dial");
    refresh();
  });
  document.getElementById("wa-number").addEventListener("input", function(e){ state.waNumber = e.target.value; refresh(); });
  document.getElementById("wa-message").addEventListener("input", function(e){ state.waMessage = e.target.value; refresh(); });

  document.getElementById("tg-input").addEventListener("input", function(e){ state.tg = e.target.value; refresh(); });
  document.getElementById("im-country").addEventListener("change", function(e){
    state.imCode = e.target.selectedOptions[0].getAttribute("data-dial");
    refresh();
  });
  document.getElementById("im-number").addEventListener("input", function(e){ state.imNumber = e.target.value; refresh(); });
  document.getElementById("im-message").addEventListener("input", function(e){ state.imMessage = e.target.value; refresh(); });

  document.getElementById("wifi-ssid").addEventListener("input", function(e){ state.wifiSsid = e.target.value; refresh(); });
  document.getElementById("wifi-pass").addEventListener("input", function(e){ state.wifiPass = e.target.value; refresh(); });
  document.getElementById("wifi-enc").addEventListener("change", function(e){
    state.wifiEnc = e.target.value;
    // an open network has no password field
    document.getElementById("wifi-pass").style.display = (state.wifiEnc === "nopass") ? "none" : "";
    refresh();
  });
  document.getElementById("wifi-hidden").addEventListener("change", function(e){ state.wifiHidden = e.target.checked; refresh(); });
  document.getElementById("vc-name").addEventListener("input", function(e){ state.vcName = e.target.value; refresh(); });
  document.getElementById("vc-phone").addEventListener("input", function(e){ state.vcPhone = e.target.value; refresh(); });
  document.getElementById("vc-email").addEventListener("input", function(e){ state.vcEmail = e.target.value; refresh(); });
  document.getElementById("vc-org").addEventListener("input", function(e){ state.vcOrg = e.target.value; refresh(); });
  document.getElementById("vc-url").addEventListener("input", function(e){ state.vcUrl = e.target.value; refresh(); });

  document.querySelectorAll(".preset").forEach(function(btn){
    btn.addEventListener("click", function(){
      document.querySelectorAll(".preset").forEach(function(b){ b.classList.remove("active"); });
      btn.classList.add("active");
      state.preset = btn.dataset.preset;
      refresh();
    });
  });

  // Accept hex with or without the leading #, and 3-digit shorthand (fff).
  function normalizeHex(v){
    v = (v || "").trim().replace(/^#/, "");
    if (/^[0-9a-fA-F]{3}$/.test(v)) v = v.replace(/(.)/g, "$1$1");
    return /^[0-9a-fA-F]{6}$/.test(v) ? "#" + v.toLowerCase() : null;
  }
  ["fg","bg"].forEach(function(which){
    var swatch = document.getElementById(which + "-color");
    var hex = document.getElementById(which + "-hex");
    swatch.addEventListener("input", function(e){
      state[which] = e.target.value;
      hex.value = e.target.value.toUpperCase();
      refresh();
    });
    hex.addEventListener("input", function(){
      var n = normalizeHex(hex.value);
      if (n){ state[which] = n; swatch.value = n; refresh(); }  // apply live, leave the text alone while typing
    });
    hex.addEventListener("blur", function(){ hex.value = state[which].toUpperCase(); });  // tidy up (or revert) on exit
    hex.addEventListener("keydown", function(e){ if (e.key === "Enter") hex.blur(); });
  });

  document.getElementById("swap-colors").addEventListener("click", function(){
    var tmp = state.fg; state.fg = state.bg; state.bg = tmp;
    document.getElementById("fg-color").value = state.fg;
    document.getElementById("bg-color").value = state.bg;
    document.getElementById("fg-hex").value = state.fg.toUpperCase();
    document.getElementById("bg-hex").value = state.bg.toUpperCase();
    refresh();
  });

  var DEFAULT_LOGO_HINT = document.getElementById("logo-hint").innerHTML;

  document.getElementById("logo-input").addEventListener("change", function(e){
    var file = e.target.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(ev){
      state.logo = ev.target.result;
      document.getElementById("logo-clear").style.display = "inline";
      document.getElementById("logo-hint").innerHTML = "Logo added. Error correction bumped to <b>High</b> so the code can take the hit and still scan.";
      refresh();
    };
    reader.readAsDataURL(file);
  });

  document.getElementById("logo-clear").addEventListener("click", function(){
    state.logo = null;
    document.getElementById("logo-input").value = "";
    this.style.display = "none";
    document.getElementById("logo-hint").innerHTML = DEFAULT_LOGO_HINT;
    refresh();
  });

  document.getElementById("transparent-bg").addEventListener("change", function(e){
    state.transparent = e.target.checked;
    checkContrast();
  });

  /* ---------- reset design (keeps your link, clears the styling) ---------- */
  document.getElementById("reset-btn").addEventListener("click", function(){
    state.preset = "classic";
    state.fg = "#1b1913";
    state.bg = "#ffffff";
    state.logo = null;
    state.transparent = false;
    document.querySelectorAll(".preset").forEach(function(b){
      b.classList.toggle("active", b.dataset.preset === "classic");
    });
    document.getElementById("fg-color").value = state.fg;
    document.getElementById("bg-color").value = state.bg;
    document.getElementById("fg-hex").value = state.fg.toUpperCase();
    document.getElementById("bg-hex").value = state.bg.toUpperCase();
    document.getElementById("logo-input").value = "";
    document.getElementById("logo-clear").style.display = "none";
    document.getElementById("logo-hint").innerHTML = DEFAULT_LOGO_HINT;
    document.getElementById("transparent-bg").checked = false;
    refresh();
  });

  /* ---------- downloads ---------- */
  function fileName(){
    if (state.type === "whatsapp") return "qr-whatsapp";
    if (state.type === "telegram") return "qr-telegram";
    if (state.type === "imessage") return "qr-text";
    if (state.type === "wifi") return "qr-wifi";
    if (state.type === "vcard") return "qr-contact";
    var host = "qr-code";
    try { if (currentData()) host = new URL(currentData()).hostname.replace(/^www\./,"").replace(/\./g,"-"); } catch(e){}
    return "qr-" + host;
  }

  var noteTimer;
  function flashDlNote(msg){
    var note = document.getElementById("dl-note");
    note.textContent = msg;
    note.classList.add("show");
    clearTimeout(noteTimer);
    noteTimer = setTimeout(function(){ note.classList.remove("show"); }, 4500);
  }
  var SAVED_LINES = [
    "Saved. Scan it once more before it goes to print.",
    "Downloaded. Keep the destination available, and test before printing.",
    "Saved. No subscription attached to this one."
  ];
  var savedIdx = 0;
  function showSaved(){ flashDlNote(SAVED_LINES[savedIdx++ % SAVED_LINES.length]); }

  document.getElementById("dl-png").addEventListener("click", async function(){
    if (!renderPreview()) return;
    if (!currentData()){
      flashDlNote("Add your link, number, network, or contact details first. The preview is only a demo code.");
      var firstField = document.querySelector("#pane-" + state.type + " input, #pane-" + state.type + " select");
      if (firstField) firstField.focus();
      return;
    }
    var size = parseInt(document.getElementById("png-size").value, 10);
    try {
      var dl = new QRCodeStyling(buildOptions(size, true));
      await dl.download({ name: fileName(), extension: "png" });
      showSaved();
    } catch(e){ flashDlNote("Download failed. Try a smaller PNG or remove the logo."); }
  });

  document.getElementById("dl-svg").addEventListener("click", async function(){
    if (!renderPreview()) return;
    if (!currentData()){
      flashDlNote("Add your link, number, network, or contact details first. The preview is only a demo code.");
      var firstField = document.querySelector("#pane-" + state.type + " input, #pane-" + state.type + " select");
      if (firstField) firstField.focus();
      return;
    }
    var opts = buildOptions(1000, true);
    opts.type = "svg";
    try {
      var dl = new QRCodeStyling(opts);
      await dl.download({ name: fileName(), extension: "svg" });
      showSaved();
    } catch(e){ flashDlNote("Download failed. Remove the logo and try again."); }
  });

  /* ---------- share to social ---------- */
  // On a phone this opens the native share sheet (Instagram, WhatsApp, Messages,
  // Stories, etc.) with the actual PNG. On desktop, where sites can't take a
  // pushed-in image, we copy the PNG to the clipboard so it's ready to paste.
  document.getElementById("share-btn").addEventListener("click", function(){ shareCode(); });
  async function shareCode(){
    if (!renderPreview()) return;
    if (!currentData()){ flashDlNote("Add your link or number first, then share your code."); return; }
    var btn = document.getElementById("share-btn");
    btn.disabled = true;
    try {
      var blob = await new QRCodeStyling(buildOptions(1000, true)).getRawData("png");
      if (!blob) throw new Error("no image");
      var file = new File([blob], fileName() + ".png", { type: "image/png" });
      if (navigator.canShare && navigator.canShare({ files: [file] })){
        await navigator.share({ files: [file], title: "My QR code", text: "Scan this QR code." });
      } else if (navigator.clipboard && window.ClipboardItem){
        await navigator.clipboard.write([ new ClipboardItem({ "image/png": blob }) ]);
        flashDlNote("Image copied. Paste it straight into your post.");
      } else {
        new QRCodeStyling(buildOptions(1000, true)).download({ name: fileName(), extension: "png" });
        flashDlNote("Saved the image. Attach it to your post.");
      }
    } catch(e){
      if (!(e && e.name === "AbortError")) flashDlNote("Couldn't open sharing here. Download the PNG and post it instead.");
    } finally {
      btn.disabled = false;
    }
  }

  /* ---------- embed on your website ---------- */
  // A self-contained snippet: the QR is an SVG baked into a data URI, so there is
  // no image file to host anywhere. It stays true to the "nothing on a server" promise.
  function altText(){
    if (state.type === "whatsapp") return "QR code to start a WhatsApp chat";
    if (state.type === "telegram") return "QR code to open a Telegram chat";
    if (state.type === "imessage") return "QR code to send a text message";
    var host = "our website";
    try { if (state.url) host = new URL(state.url).hostname.replace(/^www\./,""); } catch(e){}
    return "QR code linking to " + host;
  }
  function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

  function buildEmbed(cb){
    if (!renderPreview()){ cb(null); return; }
    var data = currentData();
    if (!data){ cb(null); return; }
    var opts = buildOptions(320, true);
    opts.type = "svg";
    var g = new QRCodeStyling(opts);
    g.getRawData("svg").then(function(blob){
      if (!blob){ cb(null); return; }
      var reader = new FileReader();
      reader.onload = function(){
        var uri = reader.result; // data:image/svg+xml;base64,....
        var img = '<img src="' + uri + '" alt="' + esc(altText()) +
                  '" width="180" height="180" style="width:180px;height:auto;max-width:100%">';
        cb('<a href="' + esc(data) + '" style="display:inline-block;line-height:0">' + img + '</a>');
      };
      reader.readAsDataURL(blob);
    }).catch(function(){ cb(null); });
  }

  var embedBox  = document.getElementById("embed-box");
  var embedCode = document.getElementById("embed-code");
  var embedHint = document.getElementById("embed-hint");
  var DEFAULT_EMBED_HINT = embedHint.textContent;

  function flashHint(msg){
    embedHint.textContent = msg;
    clearTimeout(flashHint._t);
    flashHint._t = setTimeout(function(){ embedHint.textContent = DEFAULT_EMBED_HINT; }, 2600);
  }
  function copyText(text){
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(function(){ flashHint("Copied to your clipboard."); }, selectFallback);
    } else { selectFallback(); }
  }
  function selectFallback(){
    embedCode.focus(); embedCode.select();
    try { document.execCommand("copy"); flashHint("Copied to your clipboard."); }
    catch(e){ flashHint("Press " + (/Mac/.test(navigator.platform) ? "Cmd" : "Ctrl") + "+C to copy."); }
  }

  document.getElementById("embed-btn").addEventListener("click", function(){
    buildEmbed(function(html){
      embedBox.hidden = false;
      if (!html){
        embedCode.value = "";
        embedHint.textContent = "Add your link or number first, then copy your embed code.";
        return;
      }
      embedCode.value = html;
      embedHint.textContent = DEFAULT_EMBED_HINT;
      copyText(html);
    });
  });
  document.getElementById("embed-copy").addEventListener("click", function(){
    if (embedCode.value) copyText(embedCode.value);
  });

  /* ---------- whimsy: dynamic-link wink (fires once) ---------- */
  var SHORTENERS = ["bit.ly","tinyurl.com","rebrand.ly","cutt.ly","rb.gy","ow.ly","bl.ink","is.gd","buff.ly","qrco.de","short.io","t.ly","shorturl.at","lnkd.in"];
  var winkShown = false;
  function maybeWink(v){
    var wink = document.getElementById("link-wink");
    if (!wink || winkShown || !v) return;
    var host;
    try { host = new URL(/^https?:\/\//i.test(v) ? v : "https://" + v).hostname.replace(/^www\./,"").toLowerCase(); } catch(e){ return; }
    if (SHORTENERS.indexOf(host) === -1) return;
    winkShown = true;
    wink.textContent = "That link works. Just know shorteners can vanish. The code around it won't.";
    wink.hidden = false;
    setTimeout(function(){ wink.hidden = true; }, 9000);
  }

  /* ---------- whimsy: poke the wordmark dot ---------- */
  (function(){
    var dot = document.getElementById("brand-dot");
    if (!dot) return;
    var busy = false;
    dot.addEventListener("click", function(){
      if (busy) return;
      busy = true;
      dot.classList.add("pop");
      dot.textContent = "▪";
      setTimeout(function(){ dot.textContent = "."; }, 300);
      setTimeout(function(){ dot.classList.remove("pop"); busy = false; }, 520);
    });
  })();

  /* ---------- whimsy: Konami code rains a few QR tiles ---------- */
  (function(){
    var seq = ["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"];
    var pos = 0, raining = false;
    window.addEventListener("keydown", function(e){
      var k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      if (k === seq[pos]){ pos++; if (pos === seq.length){ pos = 0; rainTiles(); } }
      else { pos = (k === seq[0]) ? 1 : 0; }
    });
    function rainTiles(){
      if (raining) return;
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      raining = true;
      var colors = ["#2563eb","#38bdf8","#14201c","#1d4ed8"];
      for (var i = 0; i < 20; i++){
        var t = document.createElement("div");
        t.className = "qr-tile";
        var size = 14 + Math.floor(Math.random() * 16);
        t.style.width = t.style.height = size + "px";
        t.style.left = Math.floor(Math.random() * 98) + "vw";
        t.style.background = colors[i % colors.length];
        t.style.animation = "qrfall " + (2.4 + Math.random() * 1.6).toFixed(2) + "s linear " + (Math.random() * 0.5).toFixed(2) + "s forwards";
        document.body.appendChild(t);
        (function(el){ setTimeout(function(){ el.remove(); }, 4600); })(t);
      }
      setTimeout(function(){ raining = false; }, 1200);
    }
  })();

  // demo code breathes "scan me" until you make it your own
  (function(){ var f = document.querySelector(".qr-frame"); if (f) f.classList.toggle("is-demo", !currentData()); })();

  checkContrast();
  renderPreview();

  window.bud = function(){
    console.log("%cQR Codes Made Easy", "font:600 16px sans-serif;color:#2563eb");
    console.log("Static codes, baked straight into the pattern. No server, no account, nothing to expire. I built it to make a point, and to be useful while I did. If it saved you a reprint, the tip jar's in the footer. Cheers, Bud.");
    return "✓ still scanning in 2035";
  };

  console.log("%cQR Codes Made Easy", "font:600 16px sans-serif;color:#2563eb");
  console.log("Yep, your codes are built right here in your browser. Your links and logo never touch a server. The only thing we count is anonymous, cookieless page views. Snoop all you like, and type bud() if you're bored. Made by Bud.");
})();

(function(){
  var words = ["brand", "product", "menu", "ad", "flyer", "design"];
  var word = document.getElementById("rotator-word");
  if (!word) return;
  var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var index = 0;
  setInterval(function(){
    if (document.hidden || motion.matches) return;
    word.textContent = words[index = (index + 1) % words.length] + ".";
  }, 2600);
})();
