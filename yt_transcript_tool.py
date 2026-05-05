#!/usr/bin/env python3
"""
YouTube Transcript Accessibility Tool
--------------------------------------
A WCAG 2.1 AA accessible transcript tool for YouTube videos.
Fetches transcripts and formats them to accessibility standards
for use in online courses.

Requirements:
    pip install flask youtube-transcript-api yt-dlp

Usage:
    python3 yt_transcript_tool.py
    → Opens http://localhost:5050 in your browser automatically.
    → Press Ctrl+C in Terminal to stop the server.
"""

import io
import re
import threading
import webbrowser
from typing import Optional

from flask import Flask, request, jsonify, send_file

import os
from datetime import datetime

PORT = int(os.environ.get("PORT", 5050))
app = Flask(__name__)

# Set once at startup — reflects when the server was last started
LAST_UPDATED = datetime.now().strftime("%B %d, %Y  %I:%M %p")

# ─── HTML UI ──────────────────────────────────────────────────────────────────

HTML_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WCAG 2.1 AA YouTube Transcript Tool</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 1rem;
      line-height: 1.6;
      color: #1a1a1a;
      background: #f0f2f0;
      min-height: 100vh;
    }

    header {
      background: #00543C;
      color: #fff;
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    header h1 { font-size: 1.15rem; }
    header p  { font-size: 0.82rem; opacity: 0.82; margin-top: 0.1rem; }
    .badge {
      font-size: 0.72rem;
      background: rgba(255,255,255,0.18);
      padding: 0.25rem 0.7rem;
      border-radius: 4px;
      font-weight: bold;
      letter-spacing: 0.04em;
    }

    main {
      max-width: 620px;
      margin: 2.5rem auto;
      padding: 0 1rem 4rem;
    }

    /* ── Step indicator ── */
    .steps {
      display: flex;
      align-items: center;
      gap: 0;
      margin-bottom: 1.75rem;
    }
    .step {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.82rem;
      color: #595959;
      flex: 1;
    }
    .step.active { color: #00543C; font-weight: bold; }
    .step.done   { color: #5a9e80; }
    .step-num {
      width: 1.6rem; height: 1.6rem;
      border-radius: 50%;
      border: 2px solid currentColor;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.75rem; font-weight: bold; flex-shrink: 0;
    }
    .step.active .step-num { background: #00543C; color: #fff; border-color: #00543C; }
    .step.done   .step-num { background: #5a9e80; color: #fff; border-color: #5a9e80; }
    .step-line { flex: 1; height: 2px; background: #ddd; margin: 0 0.5rem; }
    .step-line.done { background: #5a9e80; }

    /* ── Cards ── */
    .card {
      background: #fff;
      border-radius: 10px;
      padding: 1.5rem 1.75rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .card-title {
      font-size: 0.72rem;
      font-weight: bold;
      color: #00543C;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      padding-bottom: 0.65rem;
      border-bottom: 2px solid #eee;
      margin-bottom: 1.2rem;
    }

    /* ── Inputs ── */
    label {
      display: block;
      font-size: 0.88rem;
      font-weight: bold;
      color: #333;
      margin-bottom: 0.3rem;
    }
    label .hint {
      font-weight: normal;
      color: #595959;
      font-size: 0.78rem;
      margin-left: 0.35rem;
    }
    input[type="url"],
    input[type="text"],
    select {
      width: 100%;
      padding: 0.6rem 0.8rem;
      border: 1px solid #ccc;
      border-radius: 6px;
      font-size: 1rem;
      font-family: inherit;
      color: #1a1a1a;
      background: #fff;
      transition: border-color 0.15s;
    }
    input:focus, select:focus {
      outline: 2px solid #00543C;
      outline-offset: 1px;
      border-color: #00543C;
    }

    /* ── Step 1: URL entry ── */
    #step1 .url-row {
      display: flex;
      gap: 0.6rem;
      margin-top: 0.3rem;
    }
    #step1 .url-row input { flex: 1; min-width: 0; }

    /* ── Step 2: Review card ── */
    #step2 { display: none; margin-top: 1.25rem; }

    .video-preview {
      display: flex;
      align-items: flex-start;
      gap: 0.9rem;
      padding: 0.75rem;
      background: #f8faf9;
      border: 1px solid #d8ece5;
      border-radius: 7px;
      margin-bottom: 1.25rem;
    }
    .video-preview img {
      width: 96px;
      height: 54px;
      object-fit: cover;
      border-radius: 4px;
      flex-shrink: 0;
      background: #ccc;
    }
    .video-meta { flex: 1; min-width: 0; }
    .video-title {
      font-weight: bold;
      font-size: 0.92rem;
      line-height: 1.35;
      color: #1a1a1a;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .video-sub {
      font-size: 0.8rem;
      color: #666;
      margin-top: 0.2rem;
    }
    .chapter-badge {
      display: inline-block;
      font-size: 0.72rem;
      background: #00543C;
      color: #fff;
      padding: 0.1rem 0.45rem;
      border-radius: 3px;
      margin-left: 0.4rem;
    }

    .fields { display: flex; flex-direction: column; gap: 1rem; }

    .field-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }

    .option-group {
      display: flex;
      gap: 1.25rem;
      flex-wrap: wrap;
      margin-top: 0.2rem;
    }
    .option-group label {
      font-weight: normal;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      cursor: pointer;
      margin-bottom: 0;
    }
    .check-label {
      font-weight: normal;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      cursor: pointer;
      font-size: 0.92rem;
    }
    .check-label .note { font-size: 0.78rem; color: #595959; }

    /* ── Buttons ── */
    .btn-primary {
      width: 100%;
      padding: 0.85rem;
      background: #00543C;
      color: #fff;
      border: none;
      border-radius: 7px;
      font-size: 1rem;
      font-weight: bold;
      cursor: pointer;
      transition: background 0.15s;
      margin-top: 1.25rem;
    }
    .btn-primary:hover    { background: #003d2b; }
    .btn-primary:disabled { background: #595959; cursor: not-allowed; }

    .btn-secondary {
      padding: 0.6rem 1.1rem;
      background: #fff;
      border: 1px solid #00543C;
      color: #00543C;
      border-radius: 6px;
      font-size: 0.88rem;
      font-weight: bold;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.15s;
    }
    .btn-secondary:hover    { background: #f0f7f4; }
    .btn-secondary:disabled { opacity: 0.45; cursor: not-allowed; }

    .btn-link {
      background: none;
      border: none;
      color: #00543C;
      font-size: 0.82rem;
      cursor: pointer;
      text-decoration: underline;
      padding: 0;
      margin-top: 0.5rem;
    }

    /* ── Status / alerts ── */
    .alert {
      display: none;
      padding: 0.8rem 1rem;
      border-radius: 6px;
      font-size: 0.9rem;
      margin-top: 1rem;
    }
    .alert.loading {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      background: #e8f4f0;
      border: 1px solid #a8d4c4;
      color: #005030;
    }
    .alert.success {
      display: block;
      background: #e8f4f0;
      border: 1px solid #00543C;
      color: #003d2b;
    }
    .alert.error {
      display: block;
      background: #fce8e8;
      border: 1px solid #d9a0a0;
      color: #8b0000;
    }

    /* ── Download result ── */
    .download-result {
      display: none;
      margin-top: 1.5rem;
      padding: 1.25rem 1.5rem;
      background: #fff;
      border: 2px solid #00543C;
      border-radius: 10px;
      text-align: center;
    }
    .download-result .check {
      font-size: 2rem;
      line-height: 1;
      margin-bottom: 0.4rem;
    }
    .download-result h2 {
      font-size: 1.05rem;
      color: #00543C;
      margin-bottom: 0.25rem;
    }
    .download-result p {
      font-size: 0.85rem;
      color: #555;
    }
    .download-result .filename {
      font-family: monospace;
      font-size: 0.82rem;
      background: #f5f5f5;
      padding: 0.3rem 0.6rem;
      border-radius: 4px;
      display: inline-block;
      margin-top: 0.4rem;
      color: #333;
    }
    .another-btn {
      margin-top: 1rem;
      padding: 0.55rem 1.25rem;
      background: #00543C;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: bold;
      cursor: pointer;
    }
    .another-btn:hover { background: #003d2b; }

    /* ── Spinner ── */
    .spin {
      display: inline-block;
      width: 1em; height: 1em;
      border: 2px solid currentColor;
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.5s linear infinite;
      flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    footer {
      text-align: center;
      color: #595959;
      font-size: 0.76rem;
      margin-top: 2rem;
    }

    .tool-description {
      font-size: 1rem;
      line-height: 1.65;
      color: #333;
      margin-bottom: 0.75rem;
    }
    .tool-disclaimer {
      font-size: 0.9rem;
      color: #595959;
      font-style: italic;
      margin-bottom: 0.25rem;
    }

    /* ── Output options section ── */
    .section-divider {
      border-top: 2px solid #eee;
      padding-top: 1rem;
      margin-top: 0.25rem;
    }
    .section-heading {
      font-size: 0.72rem;
      font-weight: bold;
      color: #00543C;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      margin-bottom: 0.75rem;
    }
    .sub-heading {
      font-size: 0.82rem;
      font-weight: bold;
      color: #444;
      margin-bottom: 0.4rem;
    }
    .generate-note {
      font-size: 0.82rem;
      color: #595959;
      margin-top: 0.5rem;
      text-align: center;
    }

    /* ── Editor (Step 3) ── */
    #step3 { display: none; margin-top: 1.25rem; }

    .editor-toolbar {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
      padding: 0.6rem 0.75rem;
      background: #f8faf9;
      border: 1px solid #d0e8df;
      border-radius: 6px;
      margin-bottom: 1rem;
      font-size: 0.82rem;
    }
    .toolbar-btn {
      padding: 0.3rem 0.65rem;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 0.82rem;
      cursor: pointer;
      color: #333;
    }
    .toolbar-btn:hover { background: #f0f0f0; }
    .toolbar-hint { color: #595959; margin-left: auto; font-size: 0.78rem; }

    .meta-editor-fields {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
      padding: 0.85rem 1rem;
      background: #f8faf9;
      border: 1px solid #d0e8df;
      border-radius: 6px;
      margin-bottom: 1rem;
      font-size: 0.88rem;
    }
    .meta-field label {
      display: block;
      font-size: 0.75rem;
      font-weight: bold;
      color: #00543C;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.2rem;
    }
    .meta-field [contenteditable] {
      display: block;
      width: 100%;
      min-height: 1.4em;
      border: 1px solid #ccc;
      border-radius: 4px;
      padding: 0.3rem 0.5rem;
      font-size: 0.9rem;
      font-family: inherit;
      background: #fff;
      outline: none;
    }
    .meta-field [contenteditable]:focus {
      border-color: #00543C;
      outline: 2px solid #00543C;
      outline-offset: 1px;
    }

    .transcript-editor {
      font-family: Arial, Helvetica, sans-serif;
      font-size: 1rem;
      line-height: 1.6;
      color: #1a1a1a;
      border: 1px solid #ddd;
      border-radius: 6px;
      padding: 0.75rem 1rem;
      min-height: 200px;
      max-height: 60vh;
      overflow-y: auto;
    }
    /* Each paragraph and heading is its own editable island */
    .transcript-editor h2[contenteditable],
    .transcript-editor p[contenteditable] {
      border: 1px solid transparent;
      border-radius: 4px;
      padding: 4px 8px;
      margin-left: -8px;
      margin-right: -8px;
      cursor: text;
      outline: none;
      transition: border-color 0.12s, background 0.12s;
    }
    .transcript-editor h2[contenteditable] { margin-top: 1.5rem; margin-bottom: 0.3rem; font-size: 1.15rem; }
    .transcript-editor p[contenteditable]  { margin-bottom: 0.75em; }
    .transcript-editor h2[contenteditable]:hover,
    .transcript-editor p[contenteditable]:hover  {
      border-color: #a8d4c4;
      background: #f0f7f4;
    }
    .transcript-editor h2[contenteditable]:focus,
    .transcript-editor p[contenteditable]:focus  {
      border-color: #00543C;
      background: #fff;
      outline: 2px solid #00543C;
      outline-offset: 1px;
    }

    /* Inline delete button — appears on hover and keyboard focus */
    .para-del {
      display: none;
      margin-left: 0.6rem;
      background: #c0392b;
      color: #fff;
      border: none;
      border-radius: 3px;
      font-size: 0.72rem;
      padding: 0.1rem 0.5rem;
      cursor: pointer;
      vertical-align: middle;
      font-family: inherit;
    }
    .para-del:hover  { background: #922b21; }
    .para-del:focus  { background: #922b21; outline: 2px solid #922b21; outline-offset: 2px; }
    .transcript-editor p:hover .para-del,
    .transcript-editor p:focus-within .para-del,
    .transcript-editor h2:hover .para-del,
    .transcript-editor h2:focus-within .para-del { display: inline; }

    .editor-note {
      font-size: 0.78rem;
      color: #595959;
      margin-top: 0.4rem;
      text-align: center;
    }
  </style>
</head>
<body>

<header>
  <div>
    <h1>WCAG 2.1 AA Accessible Transcript Tool for YouTube Videos</h1>
  </div>
</header>

<main>

  <!-- Step indicator -->
  <nav class="steps" aria-label="Form progress steps">
    <div class="step active" id="stepInd1" aria-current="step" aria-label="Step 1: Enter URL — current step">
      <span class="step-num" aria-hidden="true">1</span>
      <span>Enter URL</span>
    </div>
    <div class="step-line" id="stepLine1" aria-hidden="true"></div>
    <div class="step" id="stepInd2" aria-label="Step 2: Review — not yet reached">
      <span class="step-num" aria-hidden="true">2</span>
      <span>Review</span>
    </div>
    <div class="step-line" id="stepLine2" aria-hidden="true"></div>
    <div class="step" id="stepInd3" aria-label="Step 3: Edit — not yet reached">
      <span class="step-num" aria-hidden="true">3</span>
      <span>Edit</span>
    </div>
    <div class="step-line" id="stepLine3" aria-hidden="true"></div>
    <div class="step" id="stepInd4" aria-label="Step 4: Download — not yet reached">
      <span class="step-num" aria-hidden="true">4</span>
      <span>Download</span>
    </div>
  </nav>

  <!-- ── Step 1: URL ── -->
  <div class="card" id="step1">
    <p class="tool-description">This tool was created to help you retrieve, edit, and generate <em>(English language only)</em> transcripts from YouTube for improved accessibility.</p>
    <p class="tool-disclaimer">This tool does not guarantee WCAG 2.1 AA compliance.</p>
    <div class="card-title" style="margin-top:1.25rem;">Video Source</div>
    <label for="url">Input: YouTube Video URL</label>
    <div class="url-row">
      <input type="url" id="url" placeholder="https://www.youtube.com/watch?v=…" autocomplete="off">
      <button class="btn-secondary" type="button" id="fetchBtn">Fetch Video Info</button>
    </div>
    <div class="alert" id="fetchStatus" role="status" aria-live="polite"></div>
  </div>

  <!-- ── Step 2: Review ── -->
  <div class="card" id="step2">
    <div class="card-title">Review &amp; Confirm</div>

    <!-- Thumbnail + title preview -->
    <div class="video-preview">
      <img id="thumb" src="" alt="" aria-hidden="true">
      <div class="video-meta">
        <div class="video-title" id="videoTitle"></div>
        <div class="video-sub" id="videoSub"></div>
      </div>
    </div>

    <div class="fields">

      <!-- Speaker & Publisher -->
      <div class="field-row">
        <div>
          <label for="speaker">
            Speaker
            <span class="hint">Edit for accuracy</span>
          </label>
          <input type="text" id="speaker" placeholder="Speaker name">
        </div>
        <div>
          <label for="publisher">Publisher</label>
          <input type="text" id="publisher" placeholder="Publisher name">
        </div>
      </div>

      <!-- Output Options -->
      <div class="section-divider">
        <div class="section-heading">Output Options</div>

        <div class="sub-heading">File Format</div>
        <div class="option-group">
          <label>
            <input type="radio" name="format" value="html" checked>
            HTML <span style="font-size:0.78rem;color:#595959">(accessible, recommended)</span>
          </label>
          <label>
            <input type="radio" name="format" value="txt">
            Plain Text (.txt)
          </label>
        </div>

      </div>

    </div>

    <button class="btn-primary" type="button" id="generateBtn">
      Generate Transcript
    </button>
    <p class="generate-note">After generating, you can review and edit the transcript before downloading.</p>
    <div class="alert" id="generateStatus" role="status" aria-live="polite"></div>
    <br>
    <button class="btn-link" type="button" id="resetBtn">← Start over with a different URL</button>
  </div>

  <!-- ── Step 3: Edit ── -->
  <div class="card" id="step3">
    <div class="card-title">Edit Transcript</div>

    <div class="editor-toolbar">
      <button class="toolbar-btn" type="button" id="undoBtn" title="Undo (Cmd+Z)">↩ Undo</button>
      <button class="toolbar-btn" type="button" id="redoBtn" title="Redo (Cmd+Shift+Z)">↪ Redo</button>
      <span class="toolbar-hint">Click or Tab into any paragraph or heading to edit &nbsp;·&nbsp; A red × Delete button appears at the end of each element on hover or focus</span>
    </div>

    <div class="meta-editor-fields">
      <div class="meta-field">
        <label>Speaker</label>
        <div contenteditable="true" id="editSpeaker" spellcheck="true"></div>
      </div>
      <div class="meta-field">
        <label>Publisher</label>
        <div contenteditable="true" id="editPublisher" spellcheck="true"></div>
      </div>
    </div>

    <div id="transcriptBody" class="transcript-editor"></div>
    <p class="editor-note">Click or tab into any paragraph or heading to edit it. Hover or focus to reveal the red × Delete button — usable by mouse or keyboard.</p>

    <button class="btn-primary" type="button" id="downloadBtn">Download Transcript</button>
    <div class="alert" id="downloadStatus" role="status" aria-live="polite"></div>
    <br>
    <button class="btn-link" type="button" id="backToReviewBtn">← Back to options</button>
  </div>

  <!-- ── Step 4: Download result ── -->
  <div class="download-result" id="downloadResult">
    <div class="check">✅</div>
    <h2>Transcript downloaded!</h2>
    <p>Your file should appear in your Downloads folder.</p>
    <div class="filename" id="resultFilename"></div>
    <p style="margin-top:1rem;font-size:1rem;color:#00543C;font-weight:bold;">Great! Be sure to post this transcript with your video.</p>
    <br>
    <button class="another-btn" type="button" id="anotherBtn">Generate another transcript</button>
  </div>

</main>

<footer>
  Based on WCAG 2.1 AA &amp; W3C WAI Media Accessibility Guidelines<br>
  Last updated: __LAST_UPDATED__
</footer>

<script>
  // ── Step 1: Fetch video info ────────────────────────────────────────────────
  async function fetchInfo() {
    const url = document.getElementById('url').value.trim();
    if (!url) { showAlert('fetchStatus', 'error', 'Please enter a YouTube URL.'); return; }

    const btn = document.getElementById('fetchBtn');
    btn.disabled = true;
    showAlert('fetchStatus', 'loading', '<span class="spin"></span> Fetching video info…');

    try {
      const resp = await fetch('/api/fetch-info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await resp.json();

      if (data.error) {
        showAlert('fetchStatus', 'error', '<strong>Error:</strong> ' + data.error);
        btn.disabled = false;
        return;
      }

      // Store for later
      videoData = data;

      // Populate Step 2
      populateReviewStep(data);

      // Transition UI
      hideAlert('fetchStatus');
      document.getElementById('step2').style.display = 'block';
      document.getElementById('step2').scrollIntoView({ behavior: 'smooth', block: 'start' });
      setStepState(2);

    } catch (e) {
      showAlert('fetchStatus', 'error', '<strong>Error:</strong> ' + e.message);
    } finally {
      btn.disabled = false;
    }
  }

  function populateReviewStep(data) {
    // Thumbnail
    const thumb = document.getElementById('thumb');
    if (data.video_id) {
      thumb.src = `https://img.youtube.com/vi/${data.video_id}/mqdefault.jpg`;
      thumb.alt = data.title;
    }

    // Title + subtitle
    document.getElementById('videoTitle').textContent = data.title;
    const dur = data.duration_str ? ' · ' + data.duration_str : '';
    const chaps = data.chapter_count > 0
      ? `<span class="chapter-badge">${data.chapter_count} chapter${data.chapter_count > 1 ? 's' : ''}</span>`
      : '';
    document.getElementById('videoSub').innerHTML = data.channel_name + dur + chaps;

    // Speaker and publisher both default to channel name; URL auto-filled
    document.getElementById('speaker').value   = data.channel_name || '';
    document.getElementById('publisher').value = data.channel_name || '';

    // (chapters are always included when available)
  }

  // ── Step 2: Generate & download ────────────────────────────────────────────
  // ── Helpers ────────────────────────────────────────────────────────────────
  function reset() {
    document.getElementById('url').value = '';
    document.getElementById('step2').style.display = 'none';
    document.getElementById('step3').style.display = 'none';
    document.getElementById('downloadResult').style.display = 'none';
    hideAlert('fetchStatus');
    hideAlert('generateStatus');
    hideAlert('downloadStatus');
    transcriptData = null;
    setStepState(1);
    document.getElementById('step1').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  var stepLabels = ['', 'Enter URL', 'Review', 'Edit', 'Download'];

  function setStepState(active) {
    for (var i = 1; i <= 4; i++) {
      var el = document.getElementById('stepInd' + i);
      if (!el) continue;
      if (i < active) {
        el.className = 'step done';
        el.removeAttribute('aria-current');
        el.setAttribute('aria-label', 'Step ' + i + ': ' + stepLabels[i] + ' — completed');
      } else if (i === active) {
        el.className = 'step active';
        el.setAttribute('aria-current', 'step');
        el.setAttribute('aria-label', 'Step ' + i + ': ' + stepLabels[i] + ' — current step');
      } else {
        el.className = 'step';
        el.removeAttribute('aria-current');
        el.setAttribute('aria-label', 'Step ' + i + ': ' + stepLabels[i] + ' — not yet reached');
      }
    }
    for (var j = 1; j <= 3; j++) {
      var line = document.getElementById('stepLine' + j);
      if (line) line.className = 'step-line ' + (j < active ? 'done' : '');
    }
  }

  function showAlert(id, type, html) {
    const el = document.getElementById(id);
    el.className = 'alert ' + type;
    el.innerHTML = html;
  }
  function hideAlert(id) {
    const el = document.getElementById(id);
    el.className = 'alert';
    el.innerHTML = '';
  }

  // ── State ─────────────────────────────────────────────────────────────────
  let transcriptData = null;

  // ── Wire up buttons ────────────────────────────────────────────────────────
  document.getElementById('fetchBtn').addEventListener('click', fetchInfo);
  document.getElementById('generateBtn').addEventListener('click', generate);
  document.getElementById('resetBtn').addEventListener('click', reset);
  document.getElementById('anotherBtn').addEventListener('click', reset);
  document.getElementById('downloadBtn').addEventListener('click', downloadFile);
  document.getElementById('backToReviewBtn').addEventListener('click', backToReview);
  document.getElementById('undoBtn').addEventListener('click', function() { document.execCommand('undo'); });
  document.getElementById('redoBtn').addEventListener('click', function() { document.execCommand('redo'); });
  document.getElementById('url').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') fetchInfo();
  });

  // ── Inline delete buttons (keyboard + mouse accessible) ───────────────────
  function addDeleteButtons(body) {
    body.querySelectorAll('p, h2').forEach(function(el) {
      // Avoid adding a second button if already present
      if (el.querySelector('.para-del')) return;
      var tag  = el.tagName === 'H2' ? 'heading' : 'paragraph';
      var btn  = document.createElement('button');
      btn.type = 'button';
      btn.className = 'para-del';
      btn.setAttribute('contenteditable', 'false');
      btn.setAttribute('aria-label', 'Delete this ' + tag);
      btn.textContent = '× Delete';
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        el.remove();
      });
      el.appendChild(btn);
    });
  }

  // ── Step 2 → 3: Generate (fetch transcript, open editor) ──────────────────
  async function generate() {
    const url              = document.getElementById('url').value.trim();
    const speaker          = document.getElementById('speaker').value.trim();
    const publisher        = document.getElementById('publisher').value.trim();
    const format = document.querySelector('input[name="format"]:checked').value;

    if (!speaker) { showAlert('generateStatus', 'error', 'Please enter a speaker name.'); return; }

    const btn = document.getElementById('generateBtn');
    btn.disabled = true;
    showAlert('generateStatus', 'loading', '<span class="spin"></span> Fetching and processing transcript…');

    try {
      const resp = await fetch('/api/transcript', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, speaker, publisher, format, include_chapters: true })
      });
      if (!resp.ok) {
        const err = await resp.json().catch(function() { return {}; });
        showAlert('generateStatus', 'error', '<strong>Error:</strong> ' + (err.error || 'Server error — check Terminal'));
        btn.disabled = false;
        return;
      }
      const data = await resp.json();
      if (data.error) {
        showAlert('generateStatus', 'error', '<strong>Error:</strong> ' + data.error);
        btn.disabled = false;
        return;
      }

      transcriptData = data;
      openEditor(data);
      hideAlert('generateStatus');
      setStepState(3);

    } catch (e) {
      showAlert('generateStatus', 'error', '<strong>Error:</strong> ' + e.message);
    } finally {
      btn.disabled = false;
    }
  }

  // ── Open editor with transcript data ──────────────────────────────────────
  function openEditor(data) {
    // Populate editable metadata fields
    document.getElementById('editSpeaker').textContent   = data.speaker   || '';
    document.getElementById('editPublisher').textContent = data.publisher || '';

    // Insert transcript body HTML
    var body = document.getElementById('transcriptBody');
    body.innerHTML = data.body_html || '';

    // Make EACH paragraph and heading individually contenteditable
    // (gives proper click-to-edit cursor, selection, and focus outline)
    body.querySelectorAll('p, h2').forEach(function(el) {
      el.setAttribute('contenteditable', 'true');
      el.setAttribute('spellcheck', 'true');
    });

    document.getElementById('step2').style.display = 'none';
    document.getElementById('step3').style.display = 'block';
    document.getElementById('step3').scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Add keyboard-accessible inline delete buttons
    addDeleteButtons(body);
  }

  // ── Step 3 → Back to review ───────────────────────────────────────────────
  function backToReview() {
    document.getElementById('step3').style.display = 'none';
    document.getElementById('step2').style.display = 'block';
    document.getElementById('step2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    setStepState(2);
  }

  // ── Step 3 → Download ─────────────────────────────────────────────────────
  async function downloadFile() {
    if (!transcriptData) return;

    const speaker    = document.getElementById('editSpeaker').textContent.trim();
    const publisher  = document.getElementById('editPublisher').textContent.trim();

    // Strip contenteditable attrs from a clone before sending to server
    var bodyClone = document.getElementById('transcriptBody').cloneNode(true);
    // Strip delete buttons and editing attributes before download
    bodyClone.querySelectorAll('.para-del').forEach(function(btn) { btn.remove(); });
    bodyClone.querySelectorAll('[contenteditable]').forEach(function(el) {
      el.removeAttribute('contenteditable');
      el.removeAttribute('spellcheck');
    });
    const bodyHtml = bodyClone.innerHTML;

    const btn = document.getElementById('downloadBtn');
    btn.disabled = true;
    showAlert('downloadStatus', 'loading', '<span class="spin"></span> Preparing download…');

    try {
      const resp = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_title:    transcriptData.doc_title,
          title:        transcriptData.title,
          filename:     transcriptData.filename,
          lang:         transcriptData.lang,
          format:       transcriptData.format,
          is_auto:      transcriptData.is_auto,
          duration_str: transcriptData.duration_str,
          url:          transcriptData.url,
          speaker:      speaker,
          publisher:    publisher,
          url:          transcriptData.url,
          body_html:    bodyHtml,
        })
      });

      if (!resp.ok) {
        showAlert('downloadStatus', 'error', 'Download failed — check Terminal for details');
        btn.disabled = false;
        return;
      }

      const blob = await resp.blob();
      const disposition = resp.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename[^;=\n]*=["']?([^"'\n]+)/);
      const filename = match ? match[1] : transcriptData.filename;

      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);

      hideAlert('downloadStatus');
      document.getElementById('resultFilename').textContent = filename;
      document.getElementById('downloadResult').style.display = 'block';
      document.getElementById('step3').style.display = 'none';
      document.getElementById('downloadResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
      setStepState(4);

    } catch (e) {
      showAlert('downloadStatus', 'error', '<strong>Error:</strong> ' + e.message);
    } finally {
      btn.disabled = false;
    }
  }
</script>
</body>
</html>"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> Optional[str]:
    for pattern in [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
        r"(?:embed/)([0-9A-Za-z_-]{11})",
        r"(?:shorts/)([0-9A-Za-z_-]{11})",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _oembed_fallback(url: str) -> dict:
    """Fetch basic video info via YouTube's public oEmbed API (no auth needed)."""
    import urllib.request, json as _json
    oembed = f"https://www.youtube.com/oembed?url={url}&format=json"
    with urllib.request.urlopen(oembed, timeout=10) as r:
        data = _json.loads(r.read())
    return {
        "title":        data.get("title") or "Untitled Video",
        "channel_name": data.get("author_name") or "",
        "chapters":     [],
        "duration":     0,
        "duration_str": "",
    }


def get_video_info(url: str) -> dict:
    """
    Return video metadata dict.
    Tries yt-dlp first (gives chapters + duration on local installs).
    Falls back to YouTube's public oEmbed API when yt-dlp is blocked
    (e.g. on cloud servers that YouTube treats as bots).
    """
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        duration = int(info.get("duration") or 0)
        h, rem   = divmod(duration, 3600)
        m, s     = divmod(rem, 60)
        dur_str  = (f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}") if duration else ""
        return {
            "title":        info.get("title") or "Untitled Video",
            "channel_name": info.get("channel") or info.get("uploader") or "",
            "chapters":     info.get("chapters") or [],
            "duration":     duration,
            "duration_str": dur_str,
        }
    except Exception:
        return _oembed_fallback(url)


def get_available_transcripts(video_id: str) -> list:
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        api   = YouTubeTranscriptApi()
        tlist = api.list(video_id)
        return [
            {
                "language":      t.language,
                "language_code": t.language_code,
                "is_generated":  t.is_generated,
            }
            for t in tlist
        ]
    except Exception:
        return []


def get_transcript(video_id: str, language: str) -> tuple:
    """Return (entries, is_auto, actual_language_code)."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound
    api   = YouTubeTranscriptApi()
    tlist = api.list(video_id)
    try:
        t = tlist.find_transcript([language])
    except NoTranscriptFound:
        t = next(iter(tlist))
    fetched = t.fetch()
    entries = fetched.to_raw_data()   # list of dicts: text, start, duration
    return entries, fetched.is_generated, fetched.language_code


# ─── Text processing ──────────────────────────────────────────────────────────

def fmt_tc(seconds: float) -> str:
    """Format seconds as [M:SS] or [H:MM:SS] timecode string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m}:{s:02d}]"


def clean(text: str, strip_timecodes: bool = True) -> str:
    text = re.sub(r"^>>\s*", "", text)
    if strip_timecodes:
        text = re.sub(r"\[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_paragraphs(entries: list, max_secs: float = 50.0, gap_secs: float = 0.8,
                     strip_timecodes: bool = True, five_min_markers: bool = False,
                     _marker_state: list = None) -> list:
    """
    Group transcript entries into paragraphs.
    _marker_state is a one-element list [next_marker_secs] shared across chapter calls
    so that 5-minute markers are globally sequential across the whole transcript.
    """
    if not entries:
        return []

    paragraphs, current = [], []

    # Use a shared mutable container so the counter survives across chapter calls
    if five_min_markers and _marker_state is None:
        _marker_state = [300]  # first marker at 5:00

    def prepend_marker(text: str, para_start: float) -> str:
        marker_str = ""
        while _marker_state[0] <= para_start:
            marker_str = fmt_tc(_marker_state[0])
            _marker_state[0] += 300
        return f"{marker_str} {text}" if marker_str else text

    for i, entry in enumerate(entries):
        current.append(entry)
        if i + 1 < len(entries):
            gap  = entries[i + 1]["start"] - (entry["start"] + entry["duration"])
            span = (entry["start"] + entry["duration"]) - current[0]["start"]
            if gap > gap_secs or span >= max_secs:
                text = clean(" ".join(e["text"] for e in current), strip_timecodes)
                if text:
                    if five_min_markers:
                        text = prepend_marker(text, current[0]["start"])
                    paragraphs.append(text)
                current = []
    if current:
        text = clean(" ".join(e["text"] for e in current), strip_timecodes)
        if text:
            if five_min_markers:
                text = prepend_marker(text, current[0]["start"])
            paragraphs.append(text)
    return paragraphs


def group_sections(entries: list, chapters: list, include_chapters: bool,
                   strip_timecodes: bool = True, five_min_markers: bool = False) -> list:
    # Shared marker state ensures [5:00], [10:00] etc. appear exactly once
    # across the whole transcript regardless of chapter boundaries
    marker_state = [300] if five_min_markers else None
    kw = dict(strip_timecodes=strip_timecodes, five_min_markers=five_min_markers,
              _marker_state=marker_state)

    if include_chapters and chapters:
        sections = []
        for i, ch in enumerate(chapters):
            start = ch["start_time"]
            end   = chapters[i + 1]["start_time"] if i + 1 < len(chapters) else float("inf")
            chunk = [e for e in entries if start <= e["start"] < end]
            sections.append({"heading": ch["title"], "paragraphs": split_paragraphs(chunk, **kw)})
        return sections
    return [{"heading": None, "paragraphs": split_paragraphs(entries, **kw)}]


# ─── Formatting ───────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def apply_non_speech(escaped: str) -> str:
    return re.sub(r"\[([^\]]+)\]", r'<span class="non-speech">[\1]</span>', escaped)


def safe_filename(title: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    return re.sub(r"\s+", "_", s.strip())[:100]


def build_body_html(sections: list) -> str:
    """Build just the h2/p content block from sections list."""
    lines = []
    for sec in sections:
        if sec.get("heading"):
            lines.append(f"  <h2>{esc(sec['heading'])}</h2>")
        for para in sec.get("paragraphs", []):
            if para.strip():
                lines.append(f"  <p>{apply_non_speech(esc(para))}</p>")
    return "\n".join(lines)


def assemble_html(doc_title, lang, speaker, publisher, duration_str, is_auto, url, title, body_html) -> str:
    """Wrap metadata + body HTML into a complete WCAG 2.1 AA HTML document."""
    notice = ("Auto-generated transcript. Edits have been applied for clarity."
              if is_auto else "Human-reviewed transcript.")
    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(doc_title)}</title>
  <style>
    body {{
      font-family: Arial, Helvetica, sans-serif;
      font-size: 1rem;
      line-height: 1.6;
      max-width: 75ch;
      margin: 0 auto;
      padding: 1rem;
      color: #1a1a1a;
    }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.25rem; margin-top: 2rem; margin-bottom: 0.5rem; }}
    h3 {{ font-size: 1.1rem; margin-top: 1.5rem; margin-bottom: 0.5rem; }}
    p  {{ margin-bottom: 1em; }}
    .speaker-label {{ font-weight: bold; }}
    .meta {{
      font-size: 0.9rem; color: #555555;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid #cccccc;
      padding-bottom: 1rem;
    }}
    .non-speech {{ color: #555555; font-style: italic; }}
  </style>
</head>
<body>
  <h1>{esc(doc_title)}</h1>
  <div class="meta">
    <p>
      <strong>Speaker:</strong> {esc(speaker)}<br>
      {'<strong>Publisher:</strong> ' + esc(publisher) + '<br>' if publisher else ''}
      {'<strong>Duration:</strong> ' + esc(duration_str) + '<br>' if duration_str else ''}
      <strong>URL:</strong> <a href="{esc(url)}">{esc(url)}</a><br>
      {esc(notice)}
    </p>
  </div>
{body_html}
</body>
</html>"""


def build_html_doc(title, sections, speaker, publisher, duration_str, is_auto, lang, url) -> tuple:
    doc_title = f"Transcript {title}"
    body_html = build_body_html(sections)
    html      = assemble_html(doc_title, lang, speaker, publisher, duration_str, is_auto, url, title, body_html)
    return html, f"Transcript_ {safe_filename(title)}.html"


def build_txt_doc(title, sections, speaker, duration_str, is_auto, lang, url) -> tuple:
    doc_title = f"Transcript: {title}"
    notice    = ("Auto-generated transcript. Edits have been applied for clarity."
                 if is_auto else "Human-reviewed transcript.")
    lines = [doc_title, "=" * min(len(doc_title), 80), "",
             f"Speaker: {speaker}"]
    if duration_str:
        lines.append(f"Duration: {duration_str}")
    lines += [f"Language: {lang}", f"Source:   {url}", f"Note:     {notice}", "", "-" * 60, ""]
    for sec in sections:
        if sec.get("heading"):
            h = sec["heading"].upper()
            lines += ["", h, "-" * len(h), ""]
        for para in sec.get("paragraphs", []):
            if para.strip():
                lines += [para, ""]
    return "\n".join(lines), f"Transcript_ {safe_filename(title)}.txt"


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    page = HTML_UI.replace("__LAST_UPDATED__", LAST_UPDATED)
    return page, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/fetch-info", methods=["POST"])
def fetch_info():
    """Step 1 — return video metadata + available transcript languages."""
    data     = request.get_json(silent=True) or {}
    url      = data.get("url", "").strip()
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Could not find a video ID in that URL — please check it and try again."}), 400

    try:
        info = get_video_info(url)
    except Exception as exc:
        return jsonify({"error": f"Could not reach YouTube to fetch video info: {exc}"}), 500

    transcripts = get_available_transcripts(video_id)

    return jsonify({
        "video_id":     video_id,
        "title":        info["title"],
        "channel_name": info["channel_name"],
        "duration_str": info["duration_str"],
        "chapter_count": len(info["chapters"]),
        "transcripts":  transcripts,
    })


@app.route("/api/transcript", methods=["POST"])
def generate_transcript():
    """Step 2 — fetch & process transcript, return JSON for the in-browser editor."""
    from youtube_transcript_api import NoTranscriptFound

    data             = request.get_json(silent=True) or {}
    url              = data.get("url", "").strip()
    speaker          = data.get("speaker", "").strip() or "Unknown Speaker"
    publisher        = data.get("publisher", "").strip()
    language         = "en"
    fmt              = data.get("format", "html")
    inc_chapters     = bool(data.get("include_chapters", True))
    strip_timecodes  = True    # always strip raw caption timecodes
    five_min_markers = True    # always insert clean 5-minute interval markers

    if not url:
        return jsonify({"error": "No URL provided"}), 400
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Could not extract a video ID from the URL"}), 400

    try:
        info = get_video_info(url)
    except Exception as exc:
        return jsonify({"error": f"Could not fetch video info: {exc}"}), 500

    try:
        entries, is_auto, actual_lang = get_transcript(video_id, language)
    except NoTranscriptFound:
        return jsonify({"error": f'No transcript found in "{language}" — try a different language'}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not fetch transcript: {exc}"}), 500

    sections  = group_sections(entries, info["chapters"], inc_chapters, strip_timecodes, five_min_markers)
    body_html = build_body_html(sections)
    filename  = f"Transcript_ {safe_filename(info['title'])}.{'txt' if fmt == 'txt' else 'html'}"

    return jsonify({
        "doc_title":    f"Transcript {info['title']}",
        "title":        info["title"],
        "filename":     filename,
        "lang":         actual_lang,
        "format":       fmt,
        "is_auto":      is_auto,
        "speaker":      speaker,
        "publisher":    publisher,
        "duration_str": info["duration_str"],
        "url":          url,
        "body_html":    body_html,
    })


@app.route("/api/download", methods=["POST"])
def download_transcript():
    """Step 3 — receive edited content from the browser, return final file."""
    data         = request.get_json(silent=True) or {}
    doc_title    = data.get("doc_title", "Transcript")
    title        = data.get("title", "")
    filename     = data.get("filename", "transcript.html")
    lang         = data.get("lang", "en")
    fmt          = data.get("format", "html")
    speaker      = data.get("speaker", "").strip() or "Unknown Speaker"
    publisher    = data.get("publisher", "").strip()
    duration_str = data.get("duration_str", "")
    url          = data.get("url", "")
    is_auto      = bool(data.get("is_auto", True))
    body_html    = data.get("body_html", "")

    if fmt == "txt":
        # Strip HTML tags for plain text
        import html as html_lib
        text_body = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\1\n" + "-" * 40, body_html, flags=re.DOTALL)
        text_body = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n", text_body, flags=re.DOTALL)
        text_body = re.sub(r"<[^>]+>", "", text_body)
        text_body = html_lib.unescape(text_body)
        notice    = "Auto-generated transcript. Edits have been applied for clarity." if is_auto else "Human-reviewed transcript."
        lines     = [f"Transcript: {title}", "=" * min(len(title) + 12, 80), "",
                     f"Speaker: {speaker}"]
        if duration_str:
            lines.append(f"Duration: {duration_str}")
        lines += [f"Language: {lang}", f"Source:   {url}", f"Note:     {notice}", "", "-" * 60, "", text_body.strip()]
        content  = "\n".join(lines)
        mimetype = "text/plain"
        filename = filename.replace(".html", ".txt")
    else:
        content  = assemble_html(doc_title, lang, speaker, publisher, duration_str, is_auto, url, title, body_html)
        mimetype = "text/html"

    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename, mimetype=mimetype)


# ─── Launch ───────────────────────────────────────────────────────────────────

def _open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    # Local development only — production uses gunicorn via Procfile
    print(f"\n  YouTube Transcript Accessibility Tool")
    print(f"  {'─' * 50}")
    print(f"  Opening  http://localhost:{PORT}  in your browser…")
    print(f"  Press Ctrl+C to stop.\n")
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)
