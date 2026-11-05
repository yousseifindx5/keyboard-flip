/* Shared by every page: converter demo, animated explainer, GitHub stars, theme toggle. */
(function(){
"use strict";

// ---- shared key map (English US <-> Arabic 101, lowercase keys) ----
var EN="` 1 2 3 4 5 6 7 8 9 0 - = q w e r t y u i o p [ ] \\ a s d f g h j k l ; ' z x c v b n m , . /".split(" ");
var AR="ذ 1 2 3 4 5 6 7 8 9 0 - = ض ص ث ق ف غ ع ه خ ح ج د \\ ش س ي ب ل ا ت ن م ك ط ئ ء ؤ ر لا ى ة و ز ظ".split(" ");
var toAr={},toEn={};
EN.forEach(function(k,i){toAr[k]=AR[i];if(/[^\d\-=\\]/.test(AR[i]))toEn[AR[i]]=k});

function flip(t,dir){
  var m=dir==="en"?toAr:toEn,r="",i=0;
  while(i<t.length){
    var two=t.substr(i,2);
    if(dir==="ar"&&toEn[two]){r+=toEn[two];i+=2;continue}
    var c=t[i],l=dir==="en"?c.toLowerCase():c;
    r+=m.hasOwnProperty(l)?m[l]:c;i++;
  }
  return r;
}

// ---- live converter ----
var demo=document.getElementById("converter");
if(demo){
  var dir="en",inp=document.getElementById("inp"),out=document.getElementById("out");
  var fromL=document.getElementById("fromLabel"),toL=document.getElementById("toLabel");
  var lblEn=demo.getAttribute("data-lbl-en"),lblAr=demo.getAttribute("data-lbl-ar");
  var render=function(){
    out.textContent=flip(inp.value,dir);
    fromL.textContent=dir==="en"?lblEn:lblAr;
    toL.textContent=dir==="en"?lblAr:lblEn;
    inp.dir=dir==="en"?"ltr":"rtl";
  };
  inp.addEventListener("input",render);
  document.getElementById("swap").addEventListener("click",function(){
    var o=flip(inp.value,dir);dir=dir==="en"?"ar":"en";inp.value=o;render();
  });
  render();
}

// ---- animated explainer: render(t) is a pure function of time (t in seconds, loop = 7s) ----
var anim=document.getElementById("anim");
if(anim){
  var SRC="hello world",OUT=flip(SRC,"en"),D=7;
  var elTxt=document.getElementById("animTxt"),elSel=document.getElementById("animSel"),
      elCaret=document.getElementById("animCaret"),elBody=document.getElementById("animBody"),
      k1=document.getElementById("animK1"),k2=document.getElementById("animK2"),
      cap=document.getElementById("animCap"),dots=anim.querySelectorAll(".dots i"),
      caps=[0,1,2,3].map(function(n){return anim.getAttribute("data-c"+n)||""});
  var render2=function(t){
    t=((t%D)+D)%D;
    var typed=t<0.5?0:Math.min(SRC.length,Math.floor((t-0.5)/0.12)+1);
    var flipped=t>=3.35&&t<5.25;
    elTxt.textContent=flipped?OUT:SRC.slice(0,typed);
    var p=t<2.3?0:t<2.8?(t-2.3)/0.5:t<3.35?1:0;
    elSel.style.width=(p*100)+"%";
    var typing=t<2.3,blink=Math.floor(t*2.5)%2===0;
    elCaret.style.visibility=(!flipped&&p===0&&(typing||blink))?"visible":"hidden";
    k1.className="kg"+(t>=3.1&&t<3.8?" on":"");
    k2.className="kg"+(t>=5.0&&t<5.7?" on":"");
    elBody.style.opacity=t>6.7?String(Math.max(0,1-(t-6.7)/0.3)):"1";
    var step=t<2.3?0:t<3.1?1:t<5.0?2:3;
    cap.textContent=caps[step];
    for(var i=0;i<dots.length;i++)dots[i].className=i===step?"on":"";
  };
  window.KFDemo={render:render2,duration:D,source:SRC,result:OUT};

  var capture=location.search.indexOf("capture")>-1;
  var reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
  if(capture){render2(0)}
  else if(reduce){render2(3.5)}
  else{
    var start=null,running=false,raf=0;
    var tick=function(now){
      if(!running)return;
      if(start===null)start=now;
      render2((now-start)/1000);
      raf=requestAnimationFrame(tick);
    };
    var play=function(){if(!running){running=true;start=null;raf=requestAnimationFrame(tick)}};
    var stop=function(){running=false;cancelAnimationFrame(raf)};
    if("IntersectionObserver" in window){
      new IntersectionObserver(function(es){es[0].isIntersecting?play():stop()},{threshold:.15}).observe(anim);
    }else play();
    document.addEventListener("visibilitychange",function(){document.hidden?stop():play()});
    render2(3.5);
  }
}

// ---- GitHub star count (fails silently if offline or rate-limited) ----
if(document.getElementById("stars")||document.getElementById("starsNav")||document.getElementById("starsBig")){
  fetch("https://api.github.com/repos/yousseifindx5/keyboard-flip").then(function(r){return r.json()}).then(function(d){
    if(typeof d.stargazers_count==="number"){
      ["stars","starsNav","starsBig"].forEach(function(id){
        var e=document.getElementById(id);if(e)e.textContent="· "+d.stargazers_count;
      });
    }
  }).catch(function(){});
}
var yr=document.getElementById("year");if(yr)yr.textContent=new Date().getFullYear();

// ---- light / dark toggle (remembers your choice, shared by every page) ----
var themeBtn=document.getElementById("theme");
if(themeBtn){
  var paint=function(){
    var light=document.documentElement.dataset.theme==="light";
    themeBtn.textContent=themeBtn.getAttribute(light?"data-to-dark":"data-to-light");
    themeBtn.title=themeBtn.getAttribute(light?"data-title-dark":"data-title-light");
  };
  themeBtn.addEventListener("click",function(){
    var next=document.documentElement.dataset.theme==="light"?"dark":"light";
    document.documentElement.dataset.theme=next;
    try{localStorage.setItem("theme",next)}catch(e){}
    paint();
  });
  paint();
}
})();
