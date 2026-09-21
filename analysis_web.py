#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文小说文本分析器：静态网页版（可部署到 GitHub Pages）

用法:
    python3 analysis_web.py

功能:
    在当前目录生成一个自包含的静态 index.html（无需任何服务器）:
      1. 在网页中选择本地 .txt 文档（点击或拖拽）
      2. 词频最高的十个词(全部词与实义词)
      3. 出现次数最多的五个人物及其特征词与情绪倾向
      4. 基于大连理工情感词汇本体库的情感分布(极性 + 七大情感 + 分节弧线)

    全部分析逻辑运行在浏览器端:
      - 中文分词使用浏览器原生 Intl.Segmenter
      - 情感词典在生成时内嵌进 HTML(来自 dlut_emotion.csv)
    生成的 index.html 可直接双击打开, 也可推送到 GitHub Pages。

    生成时若当前目录没有 dlut_emotion.csv, 会自动从 GitHub 下载。
    依赖: 仅 Python 标准库。
"""
import csv
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DICT_URL = ("https://raw.githubusercontent.com/yizhanmiao/DLUT-Emotionontology/"
            "master/%E6%83%85%E6%84%9F%E8%AF%8D%E6%B1%87/%E6%83%85%E6%84%9F%E8%AF%8D%E6%B1%87.csv")
DICT_PATH = os.path.join(BASE, "dlut_emotion.csv")
INDEX_PATH = os.path.join(BASE, "index.html")

GROUPS = {"乐": ["PH", "PE"], "好": ["PA", "PB", "PD", "PG", "PK"], "惊": ["PC"],
          "怒": ["NA"], "哀": ["NB", "NJ", "NH", "PF"],
          "惧": ["NC", "NI", "NG", "NL"], "恶": ["ND", "NE", "NK", "NN"]}
CODE2GROUP = {c: g for g, cs in GROUPS.items() for c in cs}

SINGLE = [("怕", "NC"), ("吓", "NC"), ("慌", "NI"), ("哭", "NB"), ("悲", "NB"),
          ("苦", "NB"), ("愁", "NB"), ("恨", "NA"), ("怨", "NA"), ("恼", "NA"),
          ("骂", "NA"), ("疯", "NE"), ("死", "NB")]

STOP = """什么 怎么 怎么样 怎样 为什么 自己 知道 看见 说道 笑道 哭道 骂道 喊道 问道 答道
说话 话里 话儿 事情 日子 样子 地方 时候 一声 一样 一边 一直 一回 一下 一点 一起
起来 过来 出来 回来 下去 上来 然后 这时 这会儿 那会儿 似乎 好像 几乎 大约 大概
可能 已经 曾经 正在 将要 不必 不用 不能 不是 不行 不够 不可 不好 如此 只好 只有
这个 那个 这些 那些 大家 别人 你们 我们 他们 她们 没有 现在 今天 明天 过去 将来
终于 应该 或者 也许 其实 果然 原来 实在 有些 一会儿 半天 什么人 什么话 什么样
怎么啦 怎么办 怎么了 看出来 看出来 听见 闻到 觉得 感到 显得 变得
就是 她的 他的 你的 我的 它的 她说 他说 我说 你说 说完 说道 二人 两人 三人""".split()

JUNK = ["起来", "不是", "回头", "原来", "实在", "不行", "不够", "不可", "作为", "自然",
        "富有", "根本", "少爷", "其实", "自言自语", "神秘", "横生", "随便", "干脆"]

FLIP = ["不", "没", "无", "别", "未", "非", "没有", "不是", "莫", "勿"]

TITLE = ["太太", "老爷", "少爷", "小姐", "丫环", "丫头", "管家", "姨太太",
         "大太太", "老太爷", "大少爷", "大小姐"]

TRAIT_STOP = ["突然", "忽然", "厉害", "普通", "一样"]

VARIANTS = {"著": "着", "裡": "里", "裏": "里", "麼": "么", "們": "们", "來": "来",
            "對": "对", "時": "时", "說": "说", "話": "话", "後": "后", "過": "过",
            "還": "还", "這": "这", "沒": "没", "發": "发", "讓": "让", "點": "点",
            "聽": "听", "問": "问", "頭": "头", "開": "开", "關": "关", "見": "见",
            "覺": "觉", "氣": "气", "馬": "马", "東": "东", "車": "车", "門": "门",
            "長": "长", "愛": "爱", "風": "风", "雲": "云", "飛": "飞", "鳥": "鸟",
            "陰": "阴", "陽": "阳", "離": "离", "顯": "显", "壞": "坏", "聲": "声",
            "餘": "余", "錢": "钱", "貴": "贵", "賣": "卖", "買": "买", "實": "实",
            "壓": "压", "礙": "碍", "獨": "独", "為": "为", "經": "经", "辦": "办",
            "動": "动", "應": "应", "該": "该", "認": "认", "識": "识", "試": "试",
            "運": "运", "遠": "远", "遇": "遇", "隨": "随", "險": "险", "雙": "双",
            "歡": "欢", "樂": "乐", "淚": "泪", "淨": "净", "準": "准", "終": "终"}


def ensure_dict():
    if os.path.exists(DICT_PATH):
        return DICT_PATH
    print("正在下载情感词典(大连理工情感词汇本体库)...")
    urllib.request.urlretrieve(DICT_URL, DICT_PATH)
    return DICT_PATH


def build_dict_js():
    ensure_dict()
    d = {}
    with open(DICT_PATH, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) < 7 or r[0].strip() in ("", "词语"):
                continue
            w = r[0].strip()
            code = r[4].strip()
            g = CODE2GROUP.get(code)
            if w and g and w not in d and len(w) <= 6:
                d[w] = g
    for w, code in SINGLE:
        d.setdefault(w, CODE2GROUP[code])
    return d


def render_js_literal(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中文小说文本分析器（静态版）</title>
<style>
 body{font-family:"Noto Sans SC","Microsoft YaHei",sans-serif;background:#f4f5f7;margin:0;color:#222}
 header{background:#2b3a4a;color:#fff;padding:18px 32px}
 header h1{margin:0;font-size:22px} header p{margin:6px 0 0;font-size:13px;opacity:.75}
 main{max-width:960px;margin:24px auto;padding:0 16px}
 .card{background:#fff;border-radius:10px;padding:20px 24px;margin-bottom:18px;
       box-shadow:0 1px 4px rgba(0,0,0,.08)}
 h2{font-size:17px;border-left:4px solid #2b6cb0;padding-left:10px;margin:4px 0 14px}
 #drop{border:2px dashed #9db4d0;border-radius:10px;padding:28px;text-align:center;
       color:#556;cursor:pointer;transition:background .2s}
 #drop:hover,#drop.over{background:#eef3fb}
 #file{display:none}
 #status{color:#666;font-size:14px;margin:10px 0 0}
 .err{color:#c0392b}
 .bar-row{display:flex;align-items:center;margin:7px 0;font-size:14px}
 .bar-label{width:110px;flex:none}
 .bar-track{flex:1;background:#eceff3;border-radius:5px;height:22px}
 .bar-fill{height:22px;border-radius:5px;background:#4c72b0;color:#fff;font-size:12px;
           line-height:22px;padding-left:8px;min-width:34px}
 .bar-val{width:56px;flex:none;text-align:right;font-variant-numeric:tabular-nums}
 .chip{display:inline-block;background:#eef2f8;border:1px solid #c9d6ea;border-radius:14px;
       padding:3px 10px;margin:2px 4px;font-size:13px}
 .chip.neg{background:#fdecec;border-color:#e8b4b4}
 .name-card{border:1px solid #e2e6ee;border-radius:8px;padding:12px 14px;margin:10px 0}
 .name-card b{font-size:16px}
 .muted{color:#888;font-size:12px}
 .grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
 @media(max-width:760px){.grid2{grid-template-columns:1fr}}
 table{width:100%;border-collapse:collapse;font-size:14px}
 td,th{padding:7px 10px;border-bottom:1px solid #eee;text-align:left}
 th{background:#f0f3f7}
 footer{text-align:center;color:#999;font-size:12px;padding:10px 0 30px}
</style>
</head>
<body>
<header>
  <h1>中文小说文本分析器</h1>
  <p>纯静态页面 · 本地分析不上传任何数据 · 词频 Top10 · 人物特征 · 词典情感分析</p>
</header>
<main>
 <div class="card">
  <h2>① 选择文本</h2>
  <div id="drop">点击选择或拖拽 .txt 文档到此处</div>
  <input type="file" id="file" accept=".txt,text/plain">
  <div id="status"></div>
 </div>
 <div id="out"></div>
 <footer>词典: 大连理工大学信息检索研究室情感词汇本体库 · 分词: 浏览器原生 Intl.Segmenter</footer>
</main>
<script>
"use strict";
var EMO_DICT = __EMO_DICT__;
var VAR_MAP = __VAR_MAP__;
var STOP = __STOP__;
var JUNK = __JUNK__;
var FLIP = __FLIP__;
var TITLE = __TITLE__;
var TRAIT_STOP = __TRAIT_STOP__;
var GROUPS = ["乐", "好", "惊", "怒", "哀", "惧", "恶"];
var POS_GROUPS = {"乐": 1, "好": 1};
var SPLIT_RE = /[。！？；\\n]+/;
var SEC_RE = /^第[一二三四五六七八九十百零〇0-9]+[节章回][^\\n]{0,10}$/m;

function normToken(t) {
  var out = "";
  for (var i = 0; i < t.length; i++) {
    var c = t[i];
    out += VAR_MAP[c] || c;
  }
  return out;
}

function tokenize(text) {
  if (typeof Intl === "undefined" || !Intl.Segmenter) return null;
  var seg = new Intl.Segmenter("zh", {granularity: "word"});
  var toks = [];
  var it = seg.segment(text)[Symbol.iterator]();
  var r;
  while (!(r = it.next()).done) {
    var s = r.value;
    var t = s.segment;
    if (/^[\\u4e00-\\u9fff]+$/.test(t)) toks.push(normToken(t));
  }
  return toks;
}

function isCJK(ch) {
  var x = ch.charCodeAt(0);
  return x >= 0x4e00 && x <= 0x9fff;
}

function rawCount(text, s) {
  var n = 0, i = 0;
  while ((i = text.indexOf(s, i)) >= 0) { n++; i += s.length; }
  return n;
}

function topWords(toks, names) {
  var cnt = {};
  toks.forEach(function (w) {
    if (w.length >= 2) cnt[w] = (cnt[w] || 0) + 1;
  });
  names.forEach(function (x) { cnt[x[0]] = x[1]; });
  var all = [], content = [];
  for (var w in cnt) {
    all.push([w, cnt[w]]);
    if (STOP.indexOf(w) < 0 && JUNK.indexOf(w) < 0) content.push([w, cnt[w]]);
  }
  all.sort(function (a, b) { return b[1] - a[1]; });
  content.sort(function (a, b) { return b[1] - a[1]; });
  return {all: all.slice(0, 10), content: content.slice(0, 10)};
}

function findNames(text) {
  var grams = {};
  function allCJK(g) {
    for (var i = 0; i < g.length; i++) if (!isCJK(g[i])) return false;
    return true;
  }
  function add(g) {
    if (g && g.length >= 2 && g.length <= 4 && allCJK(g)) grams[g] = (grams[g] || 0) + 1;
  }
  function scan(word, forward) {
    var idx = 0;
    while ((idx = text.indexOf(word, idx)) >= 0) {
      if (forward) {
        var p = idx + word.length;
        while (p < text.length && !isCJK(text[p])) p++;
        add(text.slice(p, p + 2));
        add(text.slice(p, p + 3));
      } else {
        var q = idx - 1;
        while (q >= 0 && !isCJK(text[q])) q--;
        add(text.slice(q - 1, q + 1));
        add(text.slice(q - 2, q + 1));
      }
      idx += word.length;
    }
  }
  TITLE.forEach(function (t) { scan(t, true); });
  ["说", "道", "问", "骂", "喊"].forEach(function (s) { scan(s, false); });
  var STOPCHARS = "的了着是在不我她他它们个这那就和与被把让对说也还有到去来又再便才只等得很呢吧吗啊呀么哦其之者以于是上下中里外前后各地过没请都给要会能可";
  function isBad(g) {
    for (var i = 0; i < g.length; i++) if (STOPCHARS.indexOf(g[i]) >= 0) return true;
    return false;
  }
  var cands = {};
  for (var g in grams) {
    if (grams[g] >= 5 && STOP.indexOf(g) < 0 && JUNK.indexOf(g) < 0 && !isBad(g)) cands[g] = grams[g];
  }
  var names = {};
  for (var g in cands) {
    var drop = false;
    for (var v in cands) {
      if (v !== g && v.indexOf(g) >= 0 && cands[v] >= cands[g] * 0.6) { drop = true; break; }
    }
    if (!drop) names[g] = rawCount(text, g);
  }
  var arr = [];
  for (var n in names) arr.push([n, names[n]]);
  arr.sort(function (a, b) { return b[1] - a[1]; });
  return arr.slice(0, 5);
}

function traitsFor(text, globalCnt, names) {
  var sents = text.split(SPLIT_RE);
  var nameset = {};
  names.forEach(function (x) { nameset[x[0]] = 1; });
  var pool = {}, emos = {};
  names.forEach(function (x) { pool[x[0]] = {}; emos[x[0]] = {}; });
  var seg = new Intl.Segmenter("zh", {granularity: "word"});
  sents.forEach(function (s) {
    var hit = names.filter(function (x) { return s.indexOf(x[0]) >= 0; }).map(function (x) { return x[0]; });
    if (!hit.length) return;
    var it = seg.segment(s)[Symbol.iterator]();
    var r;
    while (!(r = it.next()).done) {
      var w = normToken(r.value.segment);
      if (w.length < 2 || nameset[w] || STOP.indexOf(w) >= 0 ||
          JUNK.indexOf(w) >= 0 || TRAIT_STOP.indexOf(w) >= 0) continue;
      var g = EMO_DICT[w];
      if (!g) continue;
      hit.forEach(function (n) {
        pool[n][w] = (pool[n][w] || 0) + 1;
        emos[n][g] = (emos[n][g] || 0) + 1;
      });
    }
  });
  var out = {};
  names.forEach(function (x) {
    var n = x[0], kws = [];
    for (var w in pool[n]) {
      var c = pool[n][w];
      if (c >= 2) kws.push([w, c, c * c / Math.max(1, globalCnt[w] || 1)]);
    }
    kws.sort(function (a, b) { return b[2] - a[2]; });
    var emo = [];
    for (var g in emos[n]) emo.push([g, emos[n][g]]);
    emo.sort(function (a, b) { return b[1] - a[1]; });
    out[n] = {kws: kws.slice(0, 3).map(function (k) { return [k[0], k[1]]; }),
              emo: emo.slice(0, 2)};
  });
  return out;
}

function emotionOf(text) {
  var ms = [], m, re = new RegExp(SEC_RE.source, "gm");
  while ((m = re.exec(text)) !== null) ms.push(m);
  var parts = [];
  if (ms.length < 2) {
    parts.push([null, text]);
  } else {
    var head = text.slice(0, ms[0].index).trim();
    if (head) parts.push([null, head]);
    for (var i = 0; i < ms.length; i++) {
      var end = i + 1 < ms.length ? ms[i + 1].index : text.length;
      parts.push([ms[i][0].replace(/[^\\u4e00-\\u9fff0-9]/g, ""), text.slice(ms[i].index, end)]);
    }
  }
  var emo = {}, wcnt = {}, sections = [];
  GROUPS.forEach(function (g) { emo[g] = 0; wcnt[g] = {}; });
  var seg = new Intl.Segmenter("zh", {granularity: "word"});
  parts.forEach(function (p) {
    var label = p[0], body = p[1];
    var toks = [];
    var it = seg.segment(body)[Symbol.iterator]();
    var r;
    while (!(r = it.next()).done) {
      var t = r.value.segment;
      if (/^[\\u4e00-\\u9fff]+$/.test(t)) toks.push(normToken(t));
    }
    var pos = 0, neg = 0;
    for (var i = 0; i < toks.length; i++) {
      var base = toks[i], nudge = false;
      if (/^[不没未][\\u4e00-\\u9fff]{1,2}$/.test(base)) {
        base = base.slice(1);
        nudge = true;
      }
      var g = EMO_DICT[base];
      if (!g || JUNK.indexOf(base) >= 0) continue;
      var eff = POS_GROUPS[g] ? 1 : 2;
      if (nudge) eff = eff === 2 ? 1 : 2;
      else {
        for (var j = Math.max(0, i - 2); j < i; j++) {
          if (FLIP.indexOf(toks[j]) >= 0) { eff = eff === 2 ? 1 : 2; break; }
        }
      }
      if (eff === 1) pos++; else neg++;
      emo[g]++;
      wcnt[g][base] = (wcnt[g][base] || 0) + 1;
    }
    if (label) sections.push([label, pos, neg]);
  });
  var posT = 0, negT = 0;
  sections.forEach(function (s) { posT += s[1]; negT += s[2]; });
  var top = {};
  GROUPS.forEach(function (g) {
    var arr = [];
    for (var w in wcnt[g]) {
      if (JUNK.indexOf(w) < 0) arr.push([w, wcnt[g][w]]);
    }
    arr.sort(function (a, b) { return b[1] - a[1]; });
    top[g] = arr.slice(0, 6);
  });
  return {pos: posT, neg: negT, cats: emo, sections: sections, top: top};
}

function analyzeText(text) {
  var toks = tokenize(text);
  if (!toks) return {error: "当前浏览器不支持 Intl.Segmenter，请使用较新版本的 Chrome / Edge / Firefox / Safari"};
  var globalCnt = {};
  toks.forEach(function (w) { if (w.length >= 2) globalCnt[w] = (globalCnt[w] || 0) + 1; });
  var names = findNames(text);
  var tw = topWords(toks, names);
  var tr = traitsFor(text, globalCnt, names);
  var em = emotionOf(text);
  return {chars: text.length, all_words: tw.all, content_words: tw.content,
          names: names, traits: tr, emotion: em};
}

if (typeof document !== "undefined") {
  var drop = document.getElementById("drop");
  var fileInput = document.getElementById("file");
  var status = document.getElementById("status");
  var out = document.getElementById("out");
  drop.onclick = function () { fileInput.click(); };
  drop.ondragover = function (e) { e.preventDefault(); drop.classList.add("over"); };
  drop.ondragleave = function () { drop.classList.remove("over"); };
  drop.ondrop = function (e) {
    e.preventDefault();
    drop.classList.remove("over");
    if (e.dataTransfer.files.length) handle(e.dataTransfer.files[0]);
  };
  fileInput.onchange = function () {
    if (fileInput.files.length) handle(fileInput.files[0]);
  };

  function decode(buf) {
    try {
      return new TextDecoder("utf-8", {fatal: true}).decode(buf);
    } catch (e) {
      try {
        return new TextDecoder("gb18030").decode(buf);
      } catch (e2) {
        return new TextDecoder().decode(buf);
      }
    }
  }

  function handle(f) {
    status.textContent = "读取中: " + f.name;
    out.innerHTML = "";
    if (typeof Intl === "undefined" || !Intl.Segmenter) {
      status.innerHTML = '<span class="err">当前浏览器不支持 Intl.Segmenter，请使用较新版本的 Chrome / Edge / Firefox / Safari</span>';
      return;
    }
    var fr = new FileReader();
    fr.onload = function () {
      setTimeout(function () {
        status.textContent = "分析中，请稍候…";
        setTimeout(function () {
          try {
            var text = decode(fr.result);
            var t0 = Date.now();
            var j = analyzeText(text);
            var ms = Date.now() - t0;
            status.textContent = "完成，用时 " + ms + " ms";
            render(j);
          } catch (e) {
            status.innerHTML = '<span class="err">分析失败: ' + e.message + "</span>";
          }
        }, 30);
      }, 30);
    };
    fr.onerror = function () {
      status.innerHTML = '<span class="err">文件读取失败</span>';
    };
    fr.readAsArrayBuffer(f);
  }

  function bar(items, color) {
    var max = 1;
    items.forEach(function (i) { if (i[1] > max) max = i[1]; });
    return items.map(function (it) {
      return '<div class="bar-row"><div class="bar-label">' + it[0] +
        '</div><div class="bar-track"><div class="bar-fill" style="width:' +
        (it[1] / max * 100) + "%;" + (color ? "background:" + color : "") + '">' + it[1] +
        '</div></div><div class="bar-val">' + it[1] + "</div></div>";
    }).join("");
  }

  function render(j) {
    var h = "";
    h += '<div class="card"><h2>② 词频最高的十个词</h2><div class="grid2">' +
      "<div><b>全部词 Top10（含虚词）</b>" + bar(j.all_words) + "</div>" +
      "<div><b>实义词 Top10（去虚词）</b>" + bar(j.content_words, "#C44E52") + "</div>" +
      '</div><p class="muted">全文约 ' + j.chars + " 字</p></div>";
    h += '<div class="card"><h2>③ 出现最多的五个人物及性格特征</h2>';
    h += j.names.map(function (x) {
      var n = x[0], c = x[1], t = j.traits[n] || {kws: [], emo: []};
      var ks = t.kws.map(function (k) {
        return '<span class="chip">' + k[0] + " ×" + k[1] + "</span>";
      }).join("");
      var es = t.emo.map(function (k) {
        return '<span class="chip neg">' + k[0] + " ×" + k[1] + "</span>";
      }).join("");
      return '<div class="name-card"><b>' + n + '</b> <span style="color:#888">(出现 ' + c +
        ' 次)</span><br>' + ks + (es ? "<br>情绪倾向: " + es : "") + "</div>";
    }).join("");
    h += "</div>";
    var e = j.emotion;
    h += '<div class="card"><h2>④ 情感分布（大连理工情感词汇本体库）</h2>' +
      "<p>积极 <b>" + e.pos + "</b> 次 · 消极 <b>" + e.neg + "</b> 次 · 消极占比 <b>" +
      (100 * e.neg / Math.max(1, e.pos + e.neg)).toFixed(1) + "%</b></p>";
    var mx = 1;
    GROUPS.forEach(function (g) { if (e.cats[g] > mx) mx = e.cats[g]; });
    h += GROUPS.map(function (g) {
      var c = e.cats[g];
      var col = (g === "乐" || g === "好") ? "#4c9be8" : "#c0504d";
      return '<div class="bar-row"><div class="bar-label">' + g +
        '</div><div class="bar-track"><div class="bar-fill" style="width:' + (c / mx * 100) +
        "%;background:" + col + '">' + c + '</div></div><div class="bar-val">' + c + "</div></div>";
    }).join("");
    h += '<h2 style="margin-top:20px">分节情感弧线</h2><table><tr><th>章节</th><th>积极</th><th>消极</th><th>消极占比</th></tr>';
    h += e.sections.map(function (s) {
      return "<tr><td>" + s[0] + "</td><td>" + s[1] + "</td><td>" + s[2] + "</td><td>" +
        (100 * s[2] / Math.max(1, s[1] + s[2])).toFixed(1) + "%</td></tr>";
    }).join("");
    h += "</table>";
    h += '<p class="muted">各类高频情感词: ' + GROUPS.map(function (g) {
      return g + ": " + (e.top[g] || []).map(function (x) { return x[0] + "(" + x[1] + ")"; }).join(" ");
    }).join(" · ") + "</p>";
    h += "</div>";
    out.innerHTML = h;
  }
}
</script>
</body>
</html>
"""


def build():
    emo = build_dict_js()
    html = (HTML
            .replace("__EMO_DICT__", render_js_literal(emo))
            .replace("__VAR_MAP__", render_js_literal(VARIANTS))
            .replace("__STOP__", render_js_literal(STOP))
            .replace("__JUNK__", render_js_literal(JUNK))
            .replace("__FLIP__", render_js_literal(FLIP))
            .replace("__TITLE__", render_js_literal(TITLE))
            .replace("__TRAIT_STOP__", render_js_literal(TRAIT_STOP)))
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize(INDEX_PATH)
    print(f"已生成静态页面: {INDEX_PATH} ({size/1024:.0f} KB)")
    print("· 直接双击打开即可使用（推荐 Chrome/Edge/Firefox/Safari 新版）")
    print("· 或将 index.html 推送到 GitHub 仓库并开启 Pages")


if __name__ == "__main__":
    build()