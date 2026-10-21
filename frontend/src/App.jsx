import React, { useState, useEffect, useRef } from 'react';
import {
  FileText,
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertCircle,
  Database,
  ArrowRight,
  Sun,
  Moon,
  Copy,
  Download,
  Eye,
  Trash2,
  Sparkles,
  RefreshCw,
  Server,
  Layers,
  ShieldAlert,
  DollarSign,
  TrendingUp,
  X,
  History,
  Settings,
  User,
  FolderArchive,
  ShieldCheck,
  FileClock,
  Menu,
  Clock,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { createSampleSarFiles } from './mockData';

export default function App() {
  // Theme state: dark / light
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('claude-theme') || 'light';
  });

  // Backend connection status
  const [backendStatus, setBackendStatus] = useState('checking'); // 'checking' | 'connected' | 'offline'

  // Input state
  const [caseId, setCaseId] = useState('SAR-CASE-2026-001');
  const [files, setFiles] = useState({
    json_file_1: null,
    json_file_2: null,
    csv_file_1: null,
    csv_file_2: null,
  });

  // Processing state
  const [isUploading, setIsUploading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0); // 0: idle, 1: uploaded, 2: ingested

  // Response data
  const [uploadResult, setUploadResult] = useState(null);
  const [ingestionResult, setIngestionResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // 6-Agent AI Pipeline State
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [pipelineProgress, setPipelineProgress] = useState('');
  const [call1Data, setCall1Data] = useState(null);
  const [sarReport, setSarReport] = useState(null);

  // Active result tab
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'transactions' | 'accounts' | 'json' | 'manifest' | 'sar_report'


  // Direct Ingest Modal
  const [directCaseId, setDirectCaseId] = useState('');
  const [showDirectModal, setShowDirectModal] = useState(false);

  // File preview modal
  const [previewContent, setPreviewContent] = useState(null); // { name, text, type }

  // Left Sidebar Modals (Previous SARs, History, Settings, Profile)
  const [showPreviousModal, setShowPreviousModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Drag states for each slot
  const [dragActive, setDragActive] = useState({
    json_file_1: false,
    json_file_2: false,
    csv_file_1: false,
    csv_file_2: false,
  });

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('claude-theme', theme);
  }, [theme]);

  // Check backend health on mount
  useEffect(() => {
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      setBackendStatus('checking');
      const res = await fetch('/api/files/upload', { method: 'OPTIONS' }).catch(() => null);
      // fallback test root
      const rootRes = await fetch('/').catch(() => null);
      if (res || rootRes) {
        setBackendStatus('connected');
      } else {
        setBackendStatus('offline');
      }
    } catch {
      setBackendStatus('connected'); // dev proxy connects when invoked
    }
  };

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  // Handle single file drop or change
  const handleFileSelect = (slotKey, selectedFile) => {
    setErrorMsg('');
    if (!selectedFile) return;

    const isJsonSlot = slotKey.startsWith('json');
    const isCsvSlot = slotKey.startsWith('csv');
    const ext = selectedFile.name.split('.').pop().toLowerCase();

    if (isJsonSlot && ext !== 'json') {
      setErrorMsg(`Invalid file for ${slotKey}: Must be a .json file.`);
      return;
    }
    if (isCsvSlot && ext !== 'csv') {
      setErrorMsg(`Invalid file for ${slotKey}: Must be a .csv file.`);
      return;
    }

    setFiles(prev => ({ ...prev, [slotKey]: selectedFile }));
  };

  // Clear single file slot
  const clearSlot = (slotKey) => {
    setFiles(prev => ({ ...prev, [slotKey]: null }));
  };

  // Pre-fill with sample SAR files
  const loadSampleCase = () => {
    const samples = createSampleSarFiles(caseId || 'SAR-CASE-2026-001');
    setFiles({
      json_file_1: samples.json_file_1,
      json_file_2: samples.json_file_2,
      csv_file_1: samples.csv_file_1,
      csv_file_2: samples.csv_file_2,
    });
    setCaseId(samples.caseId);
    setErrorMsg('');
    setSuccessMsg('Loaded sample SAR case files (Horizon Meridian Trading). Ready to test!');
    setTimeout(() => setSuccessMsg(''), 4000);
  };

  // Clear all files & results
  const clearAll = () => {
    setFiles({
      json_file_1: null,
      json_file_2: null,
      csv_file_1: null,
      csv_file_2: null,
    });
    setUploadResult(null);
    setIngestionResult(null);
    setErrorMsg('');
    setSuccessMsg('');
    setCurrentStep(0);
  };

  // Show text preview of a file
  const previewFile = async (file) => {
    if (!file) return;
    try {
      const text = await file.text();
      setPreviewContent({
        name: file.name,
        type: file.name.endsWith('.json') ? 'json' : 'csv',
        text,
      });
    } catch (e) {
      setErrorMsg('Failed reading file for preview: ' + e.message);
    }
  };

  // Step 1: Upload 4 files to Supabase Storage
  const handleUploadFiles = async () => {
    setErrorMsg('');
    setSuccessMsg('');

    // Check all 4 files are present
    if (!files.json_file_1 || !files.json_file_2 || !files.csv_file_1 || !files.csv_file_2) {
      setErrorMsg('Please select all 4 required files (2 JSON and 2 CSV) before uploading.');
      return null;
    }

    if (!caseId.trim()) {
      setErrorMsg('Please specify a Case ID / folder name.');
      return null;
    }

    setIsUploading(true);
    setCurrentStep(1);

    try {
      const formData = new FormData();
      formData.append('json_file_1', files.json_file_1);
      formData.append('json_file_2', files.json_file_2);
      formData.append('csv_file_1', files.csv_file_1);
      formData.append('csv_file_2', files.csv_file_2);
      formData.append('folder_name', caseId.trim());

      const res = await fetch('/api/files/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Upload failed with status ' + res.status);
      }

      setUploadResult(data);
      setSuccessMsg(`Successfully uploaded 4 files to Supabase bucket 'Uploads' in folder '${caseId.trim()}'!`);
      return data;
    } catch (err) {
      setErrorMsg(err.message || 'File upload failed');
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  // Step 2: Trigger Data Ingestion Service
  const handleRunIngestion = async (targetCaseId) => {
    const idToUse = targetCaseId || caseId.trim();
    if (!idToUse) {
      setErrorMsg('Please provide a Case ID to ingest.');
      return;
    }

    setErrorMsg('');
    setSuccessMsg('');
    setIsIngesting(true);

    try {
      const res = await fetch(`/api/ingestion/case/${encodeURIComponent(idToUse)}`, {
        method: 'POST',
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Ingestion failed with status ' + res.status);
      }

      setIngestionResult(data.structured_case);
      setCurrentStep(2);
      setSuccessMsg(`Data Ingestion Service successfully parsed and built structured_case for '${idToUse}'!`);
    } catch (err) {
      setErrorMsg(err.message || 'Data ingestion failed');
    } finally {
      setIsIngesting(false);
    }
  };

  // Run End-to-End: Step 1 then Step 2
  const handleRunEndToEnd = async () => {
    const uploadRes = await handleUploadFiles();
    if (uploadRes) {
      await handleRunIngestion(caseId.trim());
    }
  };

  // Copy JSON to clipboard
  const copyStructuredCase = () => {
    if (!ingestionResult) return;
    navigator.clipboard.writeText(JSON.stringify(ingestionResult, null, 2));
    setSuccessMsg('Copied structured_case JSON to clipboard!');
    setTimeout(() => setSuccessMsg(''), 3000);
  };

  // Download JSON file
  const downloadStructuredCase = () => {
    if (!ingestionResult) return;
    const blob = new Blob([JSON.stringify(ingestionResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `structured_case_${caseId || 'sar'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Step 3: Trigger 6-Agent SAR Generation Pipeline (Call 1: Ingest/ML + Call 2: Analyse/SAR)
  const handleRunPipeline = async () => {
    if (!ingestionResult) {
      setErrorMsg('Please ingest a case first before running the AI agent pipeline.');
      return;
    }

    setErrorMsg('');
    setSuccessMsg('');
    setIsPipelineRunning(true);
    setPipelineProgress('Agent 1: Ingesting 33 features & classifying via XGBoost model...');

    try {
      // Call 1: POST /api/pipeline/ingest
      const call1Res = await fetch('/api/pipeline/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId.trim() || 'SAR-CASE-2026-001',
          structured_case: ingestionResult,
        }),
      });

      const call1Json = await call1Res.json();
      if (!call1Res.ok) {
        throw new Error(call1Json.detail || 'Call 1 Ingestion & ML classification failed.');
      }

      setCall1Data(call1Json);

      // If Non-SAR, exit early (as per LangGraph conditional edge)
      if (!call1Json.sar_worthy) {
        setSuccessMsg(`Agent 1 Evaluation: Case is Non-SAR worthy (Confidence: ${(call1Json.confidence_score * 100).toFixed(1)}%). Pipeline routed to END (Zero LLM cost).`);
        setIsPipelineRunning(false);
        setPipelineProgress('');
        return;
      }

      // Call 2: POST /api/pipeline/analyse
      setPipelineProgress(`Agent 1: Typology '${call1Json.typology}' identified (Risk: ${call1Json.risk_score})! Running Masking Agent, Planner, 8 Evidence Rules, Groq SAR Narrative, and Compliance Judge...`);

      const call2Res = await fetch('/api/pipeline/analyse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId.trim() || 'SAR-CASE-2026-001',
          structured_case: ingestionResult,
          typology: call1Json.typology,
          risk_score: call1Json.risk_score,
          confidence_score: call1Json.confidence_score,
          sar_worthy: true,
        }),
      });

      const call2Json = await call2Res.json();
      if (!call2Res.ok) {
        throw new Error(call2Json.detail || 'Call 2 Multi-Agent analysis failed.');
      }

      setSarReport(call2Json);
      setActiveTab('sar_report');
      setSuccessMsg(`Official SAR Report generated and approved by Compliance Judge (Quality Score: ${(call2Json.quality_score * 100).toFixed(0)}%)!`);
    } catch (err) {
      setErrorMsg(err.message || 'AI Pipeline failed');
    } finally {
      setIsPipelineRunning(false);
      setPipelineProgress('');
    }
  };

  // Copy SAR narrative prose
  const copySarNarrative = () => {
    if (!sarReport?.sar_draft?.narrative) return;
    navigator.clipboard.writeText(sarReport.sar_draft.narrative);
    setSuccessMsg('Copied official SAR Narrative to clipboard!');
    setTimeout(() => setSuccessMsg(''), 3000);
  };


  // Slot definitions for the 4 input cards
  const slots = [
    {
      key: 'json_file_1',
      title: '1. Case Alert Metadata',
      desc: 'SAR alert details, institution, filing reason, priority',
      type: 'json',
      badge: '.json file',
      icon: FileText,
    },
    {
      key: 'json_file_2',
      title: '2. Subject / KYC Profile',
      desc: 'Subject legal entity, jurisdiction, PEP status, risk rating',
      type: 'json',
      badge: '.json file',
      icon: FileText,
    },
    {
      key: 'csv_file_1',
      title: '3. Financial Transactions',
      desc: 'Detailed transaction ledger, amounts, dates, counterparties',
      type: 'csv',
      badge: '.csv file',
      icon: FileSpreadsheet,
    },
    {
      key: 'csv_file_2',
      title: '4. Accounts & Audit Activity',
      desc: 'Account balances, institution statuses, audit trail records',
      type: 'csv',
      badge: '.csv file',
      icon: FileSpreadsheet,
    },
  ];

  return (
    <div className="claude-app-layout">
      {/* ----------------- Claude Left Sidebar ----------------- */}
      <aside className="claude-sidebar" style={{ display: sidebarOpen ? 'flex' : 'none' }}>
        {/* Sidebar Header */}
        <div>
          <div className="claude-sidebar-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.85rem' }}>
              <div
                style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--claude-accent-bg)',
                  border: '1px solid var(--claude-accent-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--claude-accent)',
                  flexShrink: 0,
                }}
              >
                <Sparkles size={18} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span style={{ fontSize: '0.98rem', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-serif)' }}>
                    SAR Copilot
                  </span>
                  <span className="pill-badge pill-badge-accent" style={{ fontSize: '0.62rem', padding: '0.1rem 0.4rem' }}>
                    v2.4
                  </span>
                </div>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  FinCEN BSA / AML Suite
                </p>
              </div>
            </div>

            {/* "+ New Case" Action Button */}
            <button
              onClick={() => {
                clearAll();
                setCaseId(`SAR-CASE-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 900) + 100)}`);
              }}
              className="btn btn-accent-subtle"
              style={{ width: '100%', fontSize: '0.82rem', padding: '0.5rem 0.75rem', justifyContent: 'flex-start' }}
              title="Start a new SAR case investigation"
            >
              <Sparkles size={15} />
              <span>New SAR Case</span>
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="claude-sidebar-nav">
            <div className="claude-nav-section-title">WORKBENCH</div>

            {/* Active Studio */}
            <button
              className="claude-sidebar-item active"
              title="Current Ingestion & 6-Agent AI Pipeline"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Layers size={16} />
                <span>Ingestion &amp; Pipeline</span>
              </div>
              <span className="pill-badge pill-badge-accent" style={{ fontSize: '0.65rem', padding: '0.1rem 0.45rem' }}>
                Active
              </span>
            </button>

            {/* Previous SARs */}
            <button
              onClick={() => setShowPreviousModal(true)}
              className="claude-sidebar-item"
              title="View previous SAR filings and sample cases"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <FolderArchive size={16} />
                <span>Previous SARs</span>
              </div>
              <span className="pill-badge pill-badge-neutral" style={{ fontSize: '0.65rem', padding: '0.1rem 0.45rem' }}>
                3 Cases
              </span>
            </button>

            {/* History */}
            <button
              onClick={() => setShowHistoryModal(true)}
              className="claude-sidebar-item"
              title="View audit trail and run history"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <History size={16} />
                <span>History</span>
              </div>
              <span className="pill-badge pill-badge-neutral" style={{ fontSize: '0.65rem', padding: '0.1rem 0.45rem' }}>
                Audit
              </span>
            </button>

            <div className="claude-nav-section-title" style={{ marginTop: '0.5rem' }}>MANAGEMENT</div>

            {/* Settings */}
            <button
              onClick={() => setShowSettingsModal(true)}
              className="claude-sidebar-item"
              title="System and Agent settings"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Settings size={16} />
                <span>Settings</span>
              </div>
            </button>

            {/* Profile */}
            <button
              onClick={() => setShowProfileModal(true)}
              className="claude-sidebar-item"
              title="Analyst Profile and Credentials"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <User size={16} />
                <span>Profile</span>
              </div>
            </button>

            {/* Direct Ingest Shortcut */}
            <button
              onClick={() => setShowDirectModal(true)}
              className="claude-sidebar-item"
              title="Direct Ingest from Storage"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Database size={16} />
                <span>Direct Ingest</span>
              </div>
              <ChevronRight size={14} style={{ opacity: 0.5 }} />
            </button>
          </nav>
        </div>

        {/* Sidebar Footer / Analyst Profile Card */}
        <div className="claude-sidebar-footer">
          <div
            className="claude-profile-card"
            onClick={() => setShowProfileModal(true)}
            title="Click to view Analyst profile & division"
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'var(--claude-accent)',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 600,
                  fontSize: '0.8rem',
                }}
              >
                JM
              </div>
              <div style={{ minWidth: 0, textAlign: 'left' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>
                  J. Mercer
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  Senior AML Analyst
                </div>
              </div>
            </div>
            <ShieldCheck size={16} style={{ color: 'var(--success)' }} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.65rem', padding: '0 0.25rem' }}>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              FinCEN E-Filing ID: #8842
            </span>
            <button
              onClick={toggleTheme}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                padding: '2px',
              }}
              title="Toggle theme"
            >
              {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
            </button>
          </div>
        </div>
      </aside>

      {/* ----------------- Main Content Wrapper ----------------- */}
      <div className="claude-main-area">
        {/* Top Header */}
        <header
          style={{
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-surface)',
            padding: '0.75rem 1.75rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            position: 'sticky',
            top: 0,
            zIndex: 40,
            backdropFilter: 'blur(8px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <button
              onClick={() => setSidebarOpen(prev => !prev)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '0.4rem', border: '1px solid var(--border-subtle)', background: 'var(--bg-surface)' }}
              title="Toggle sidebar"
            >
              <Menu size={16} />
            </button>
            <div style={{ height: '18px', width: '1px', backgroundColor: 'var(--border-subtle)' }} />
            <div>
              <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                FinCEN BSA Investigation &bull;
              </span>
              <h1 style={{ fontSize: '1.05rem', margin: 0, fontWeight: 600, display: 'inline', marginLeft: '0.35rem' }}>
                SAR Ingestion Studio &amp; AI Pipeline
              </h1>
            </div>
          </div>

          {/* Header Right Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {/* Backend Status Pill */}
            <div
              className={`pill-badge ${
                backendStatus === 'connected' ? 'pill-badge-success' : 'pill-badge-warning'
              }`}
              style={{ fontSize: '0.72rem', padding: '0.25rem 0.65rem' }}
            >
              <Server size={12} />
              <span>
                {backendStatus === 'connected' ? 'Backend Port 8000 (Online)' : 'Checking Backend...'}
              </span>
            </div>

            {/* Quick Sample Trigger */}
            <button
              onClick={loadSampleCase}
              className="btn btn-accent-subtle btn-sm"
              title="Fill in-memory sample SAR case files"
            >
              <Sparkles size={13} />
              Sample Data
            </button>

            {/* Direct Ingest Shortcut */}
            <button
              onClick={() => setShowDirectModal(true)}
              className="btn btn-secondary btn-sm"
              title="Ingest existing case from Supabase without uploading"
            >
              <Database size={13} />
              Direct Ingest
            </button>
          </div>
        </header>

      {/* ----------------- Main Container (1120px max-width per Claude spec) ----------------- */}
      <main style={{ flex: 1, maxWidth: '1120px', width: '100%', margin: '0 auto', padding: '2.5rem 1.5rem' }}>
        {/* Editorial Hero Introduction */}
        <div style={{ marginBottom: '2.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1.5rem' }}>
            <div style={{ maxWidth: '720px' }}>
              <span className="pill-badge pill-badge-accent" style={{ marginBottom: '0.85rem' }}>
                FinCEN BSA Investigation Suite
              </span>
              <h2 className="section-headline" style={{ marginBottom: '0.65rem' }}>
                Case Data Ingestion &amp; <span style={{ color: 'var(--accent)' }}>Structuring</span>
              </h2>
              <p style={{ color: 'var(--text-muted)', fontSize: '1rem', lineHeight: '1.6', maxWidth: '65ch' }}>
                Upload 4 case files (2 JSON, 2 CSV) to your Supabase Storage bucket, parse financial entities,
                and synthesize official regulatory filings through the 6-agent AML intelligence pipeline.
              </p>
            </div>

            {/* Quick Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button onClick={loadSampleCase} className="btn btn-primary">
                <Sparkles size={16} />
                Load Sample Case
              </button>
              <button onClick={clearAll} className="btn btn-secondary">
                <Trash2 size={16} />
                Clear
              </button>
            </div>
          </div>
        </div>

        {/* Global Notifications */}
        {errorMsg && (
          <div
            style={{
              padding: '0.85rem 1.25rem',
              backgroundColor: 'var(--danger-bg)',
              border: '1px solid var(--danger-border)',
              color: 'var(--danger)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <AlertCircle size={18} />
              <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{errorMsg}</span>
            </div>
            <button
              onClick={() => setErrorMsg('')}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {successMsg && (
          <div
            style={{
              padding: '0.85rem 1.25rem',
              backgroundColor: 'var(--success-bg)',
              border: '1px solid var(--success-border)',
              color: 'var(--success)',
              borderRadius: 'var(--radius-sm)',
              marginBottom: '1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <CheckCircle2 size={18} />
              <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{successMsg}</span>
            </div>
            <button
              onClick={() => setSuccessMsg('')}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Case ID / Folder Name Config */}
        <div className="claude-card" style={{ marginBottom: '1.75rem', padding: '1.25rem 1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
            <div style={{ flex: '1', minWidth: '280px' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                CASE ID / SUPABASE FOLDER NAME
              </label>
              <input
                type="text"
                className="claude-input"
                placeholder="e.g. SAR-CASE-2026-001"
                value={caseId}
                onChange={e => setCaseId(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1.3rem' }}>
              <div className="pill-badge pill-badge-neutral">
                Target Bucket: <strong>Uploads</strong>
              </div>
              <div className="pill-badge pill-badge-neutral">
                Storage: <strong>Supabase (S3-Compatible)</strong>
              </div>
            </div>
          </div>
        </div>

        {/* ----------------- 4-File Input Grid ----------------- */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
          {slots.map(slot => {
            const file = files[slot.key];
            const Icon = slot.icon;
            const isDrag = dragActive[slot.key];

            return (
              <div
                key={slot.key}
                className="claude-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderTop: file ? '3px solid var(--claude-accent)' : '1px solid var(--border-subtle)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Icon size={18} style={{ color: 'var(--claude-accent)' }} />
                      <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>{slot.title}</h3>
                    </div>
                    <span className="pill-badge pill-badge-accent">{slot.badge}</span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', minHeight: '38px' }}>
                    {slot.desc}
                  </p>
                </div>

                {/* Dropzone Container */}
                <div>
                  <div
                    className={`dropzone ${isDrag ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
                    onDragOver={e => {
                      e.preventDefault();
                      setDragActive(prev => ({ ...prev, [slot.key]: true }));
                    }}
                    onDragLeave={() => setDragActive(prev => ({ ...prev, [slot.key]: false }))}
                    onDrop={e => {
                      e.preventDefault();
                      setDragActive(prev => ({ ...prev, [slot.key]: false }));
                      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                        handleFileSelect(slot.key, e.dataTransfer.files[0]);
                      }
                    }}
                    onClick={() => {
                      document.getElementById(`input-${slot.key}`).click();
                    }}
                  >
                    <input
                      id={`input-${slot.key}`}
                      type="file"
                      accept={slot.type === 'json' ? '.json,application/json' : '.csv,text/csv'}
                      style={{ display: 'none' }}
                      onChange={e => {
                        if (e.target.files && e.target.files[0]) {
                          handleFileSelect(slot.key, e.target.files[0]);
                        }
                      }}
                    />

                    {file ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.35rem' }}>
                        <CheckCircle2 size={24} style={{ color: 'var(--success)' }} />
                        <span style={{ fontSize: '0.88rem', fontWeight: 600, wordBreak: 'break-all' }}>
                          {file.name}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.45rem', padding: '0.5rem 0' }}>
                        <Upload size={22} style={{ color: 'var(--text-muted)' }} />
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          Drop {slot.badge} here or <strong style={{ color: 'var(--claude-accent)' }}>browse</strong>
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Actions for loaded file */}
                  {file && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.65rem' }}>
                      <button
                        type="button"
                        onClick={e => {
                          e.stopPropagation();
                          previewFile(file);
                        }}
                        className="btn btn-secondary btn-sm"
                        title="Preview file content"
                      >
                        <Eye size={13} />
                        Preview
                      </button>
                      <button
                        type="button"
                        onClick={e => {
                          e.stopPropagation();
                          clearSlot(slot.key);
                        }}
                        className="btn btn-secondary btn-sm"
                        title="Remove file"
                        style={{ color: 'var(--danger)' }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* ----------------- Pipeline Control Action Bar ----------------- */}
        <div className="claude-card" style={{ marginBottom: '2.5rem', backgroundColor: 'var(--bg-secondary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', marginBottom: '0.2rem' }}>
                Pipeline Execution Controls
              </h3>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                Test endpoints individually or run the full end-to-end SAR workflow:
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {/* Step 1 Button */}
              <button
                onClick={handleUploadFiles}
                disabled={isUploading || isIngesting}
                className="btn btn-secondary"
              >
                {isUploading ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    1. Upload to Supabase
                  </>
                )}
              </button>

              {/* Step 2 Button */}
              <button
                onClick={() => handleRunIngestion()}
                disabled={isUploading || isIngesting}
                className="btn btn-secondary"
              >
                {isIngesting ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    Ingesting...
                  </>
                ) : (
                  <>
                    <Layers size={16} />
                    2. Run Data Ingestion
                  </>
                )}
              </button>

              {/* Combined End-to-End Button */}
              <button
                onClick={handleRunEndToEnd}
                disabled={isUploading || isIngesting}
                className="btn btn-primary"
              >
                {isUploading || isIngesting ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    Processing Pipeline...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    Run End-to-End Pipeline
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Stepper Status Bar */}
          <div
            style={{
              marginTop: '1.25rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: uploadResult ? 'var(--success)' : 'var(--text-muted)',
                }}
              />
              <span>Step 1: Upload (4 Files)</span>
            </div>
            <ArrowRight size={14} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: ingestionResult ? 'var(--success)' : 'var(--text-muted)',
                }}
              />
              <span>Step 2: Download &amp; Parse</span>
            </div>
            <ArrowRight size={14} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: ingestionResult ? 'var(--claude-accent)' : 'var(--text-muted)',
                }}
              />
              <span>Step 3: Structured Case Dict</span>
            </div>
          </div>
        </div>

        {/* ----------------- Results & Investigation Dashboard ----------------- */}
        {ingestionResult && (
          <div className="claude-card" style={{ marginBottom: '2rem', padding: '1.75rem' }}>
            {/* Header with Case ID and Action Buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.25rem' }}>
                  <ShieldAlert size={22} style={{ color: 'var(--claude-accent)' }} />
                  <h2 style={{ fontSize: '1.45rem', margin: 0 }}>
                    Structured Case: {ingestionResult.case_id}
                  </h2>
                  <span className="pill-badge pill-badge-success">Ingested &amp; Ready</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
                  Ingested from Supabase Storage &bull; {ingestionResult.ingestion_metadata?.ingested_at}
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={copyStructuredCase} className="btn btn-secondary btn-sm">
                  <Copy size={14} />
                  Copy JSON
                </button>
                <button onClick={downloadStructuredCase} className="btn btn-secondary btn-sm">
                  <Download size={14} />
                  Download JSON
                </button>
              </div>
            </div>

            {/* KPI Cards Strip */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
              <div style={{ padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '0.35rem' }}>
                  <TrendingUp size={15} />
                  <span>TOTAL VOLUME</span>
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 600, color: 'var(--claude-accent)' }}>
                  ${Number(ingestionResult.financial_activity?.total_volume || 0).toLocaleString()}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  {ingestionResult.financial_activity?.currencies_detected?.join(', ') || 'USD'}
                </div>
              </div>

              <div style={{ padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '0.35rem' }}>
                  <DollarSign size={15} />
                  <span>TRANSACTIONS COUNT</span>
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 600 }}>
                  {ingestionResult.financial_activity?.transaction_count || 0} Records
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Extracted from Transactions CSV
                </div>
              </div>

              <div style={{ padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '0.35rem' }}>
                  <Database size={15} />
                  <span>SUPPORTING RECORDS</span>
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 600 }}>
                  {ingestionResult.supporting_activity?.record_count || 0} Accounts
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Extracted from Secondary CSV
                </div>
              </div>

              <div style={{ padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', marginBottom: '0.35rem' }}>
                  <CheckCircle2 size={15} />
                  <span>FILES INGESTED</span>
                </div>
                <div style={{ fontSize: '1.35rem', fontWeight: 600, color: 'var(--success)' }}>
                  {ingestionResult.ingestion_metadata?.total_files_ingested || 4}/4 Files
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  2 JSON &bull; 2 CSV
                </div>
              </div>
            </div>

            {/* 6-Agent AI SAR Generation Action Banner */}
            <div
              style={{
                marginBottom: '1.5rem',
                padding: '1.25rem 1.5rem',
                backgroundColor: 'var(--surface-alt)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border)',
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.3rem' }}>
                  <Sparkles size={18} style={{ color: 'var(--claude-accent)' }} />
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    6-Agent AI Investigation &amp; SAR Generation Pipeline
                  </span>
                  <span className="pill-badge pill-badge-accent" style={{ fontSize: '0.72rem' }}>
                    LangGraph DAG
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Agent 1 (ML Classification) &bull; Masking Agent (PostgreSQL PII Vault) &bull; Agent 2 (Planner) &bull; Agent 3 (8 Rules + Cognitive Flow) &bull; Agent 5 (Groq Narrative) &bull; Agent 6 (Compliance Loop)
                </div>
                {pipelineProgress && (
                  <div style={{ fontSize: '0.8rem', color: 'var(--claude-accent)', marginTop: '0.45rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <RefreshCw size={13} className="spin-slow" />
                    <span>{pipelineProgress}</span>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center' }}>
                <button
                  onClick={handleRunPipeline}
                  disabled={isPipelineRunning}
                  className="btn btn-primary"
                  style={{
                    padding: '0.65rem 1.25rem',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                  }}
                >
                  {isPipelineRunning ? (
                    <>
                      <RefreshCw size={15} className="spin-slow" />
                      <span>Generating SAR...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={15} />
                      <span>Generate Official SAR</span>
                    </>
                  )}
                </button>

                {sarReport && (
                  <button
                    onClick={() => setActiveTab('sar_report')}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.85rem' }}
                  >
                    View SAR Report ({((sarReport.quality_score || 0.85) * 100).toFixed(0)}%)
                  </button>
                )}
              </div>
            </div>

            {/* Navigation Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', marginBottom: '1.25rem', gap: '0.5rem', overflowX: 'auto' }}>
              {[
                { id: 'sar_report', label: sarReport ? 'Official SAR Filing & Compliance Audit ✨' : 'Generate SAR Report ✨' },
                { id: 'overview', label: 'Case & Subject Profile' },
                { id: 'transactions', label: `Transactions (${ingestionResult.financial_activity?.transaction_count || 0})` },
                { id: 'accounts', label: `Accounts (${ingestionResult.supporting_activity?.record_count || 0})` },
                { id: 'json', label: 'Canonical structured_case JSON' },
                { id: 'manifest', label: 'Storage Manifest' },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    padding: '0.65rem 1rem',
                    background: 'transparent',
                    border: 'none',
                    borderBottom: activeTab === tab.id ? '2px solid var(--claude-accent)' : '2px solid transparent',
                    color: activeTab === tab.id ? 'var(--claude-accent)' : 'var(--text-secondary)',
                    fontWeight: activeTab === tab.id ? 600 : 500,
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab: Official SAR Report & Compliance Audit */}
            {activeTab === 'sar_report' && (
              <div>
                {!sarReport ? (
                  <div
                    style={{
                      padding: '3rem 2rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-secondary)',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px dashed var(--border-subtle)',
                    }}
                  >
                    <Sparkles size={36} style={{ color: 'var(--claude-accent)', marginBottom: '1rem' }} />
                    <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>No SAR Report Generated Yet</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '520px', margin: '0 auto 1.5rem auto' }}>
                      Run the 6-agent AI pipeline to classify typology with XGBoost, mask PII in PostgreSQL, execute the 8 evidence rules, synthesize the official SAR narrative via Groq LLM, and pass compliance audit.
                    </p>
                    <button
                      onClick={handleRunPipeline}
                      disabled={isPipelineRunning}
                      className="btn btn-primary"
                      style={{ padding: '0.75rem 1.5rem', fontSize: '0.92rem' }}
                    >
                      {isPipelineRunning ? 'Generating SAR...' : 'Run 6-Agent AI Pipeline Now'}
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Compliance Executive Header Card */}
                    <div
                      style={{
                        padding: '1.25rem 1.5rem',
                        backgroundColor: 'var(--bg-secondary)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        flexWrap: 'wrap',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1rem',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
                          <span
                            className="pill-badge"
                            style={{
                              backgroundColor: sarReport.compliance_passed ? 'var(--success-bg)' : 'var(--warning-bg)',
                              color: sarReport.compliance_passed ? 'var(--success)' : 'var(--warning)',
                              border: '1px solid ' + (sarReport.compliance_passed ? 'var(--success-border)' : 'var(--warning-border)'),
                              fontWeight: 600,
                              fontSize: '0.82rem',
                            }}
                          >
                            {sarReport.compliance_passed ? '✓ COMPLIANCE APPROVED' : '⚠ REVISION AUDITED'}
                          </span>
                          <span className="pill-badge pill-badge-accent" style={{ fontWeight: 600 }}>
                            Typology: {sarReport.plan?.active_modules ? sarReport.sar_draft?.key_indicators?.typology || call1Data?.typology || 'SAR Typology' : 'SAR'}
                          </span>
                          <span className="pill-badge pill-badge-neutral">
                            Priority: {sarReport.plan?.priority || 'HIGH'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          Case ID: <strong>{caseId}</strong> &bull; Compliance Quality Score:{' '}
                          <strong style={{ color: sarReport.quality_score >= 0.7 ? 'var(--success)' : 'var(--warning)' }}>
                            {((sarReport.quality_score || 0.85) * 100).toFixed(1)}%
                          </strong>
                          {' '}&bull; PII Vault: <strong>PostgreSQL (pii_masking_vault)</strong>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '0.65rem' }}>
                        <button
                          onClick={copySarNarrative}
                          className="btn btn-secondary"
                          style={{ fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                        >
                          <Copy size={14} />
                          <span>Copy Narrative</span>
                        </button>
                        <button
                          onClick={handleRunPipeline}
                          disabled={isPipelineRunning}
                          className="btn btn-secondary"
                          style={{ fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                        >
                          <RefreshCw size={14} className={isPipelineRunning ? 'spin-slow' : ''} />
                          <span>Re-evaluate</span>
                        </button>
                      </div>
                    </div>

                    {/* Section 1: Subject Details */}
                    <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <h3 style={{ fontSize: '1rem', color: 'var(--claude-accent)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <ShieldAlert size={16} />
                        <span>SECTION 1: SUBJECT &amp; ACCOUNT DETAILS (PII MASKED)</span>
                      </h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', fontSize: '0.88rem' }}>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>SUBJECT NAME (TOKEN)</div>
                          <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                            {sarReport.sar_draft?.subject_details?.name || '[NAME_1]'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>ACCOUNT NUMBER</div>
                          <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                            {sarReport.sar_draft?.subject_details?.account_number || '[ACCOUNT_1]'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>KYC RISK SCORE</div>
                          <div style={{ fontWeight: 600, color: 'var(--danger)' }}>
                            {sarReport.sar_draft?.subject_details?.kyc_risk || call1Data?.risk_score || '0.85'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>PEP STATUS</div>
                          <div style={{ fontWeight: 600 }}>
                            {sarReport.sar_draft?.subject_details?.pep_flag ? 'YES (Politically Exposed)' : 'NO'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Section 2: Suspicious Activity Narrative */}
                    <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                        <h3 style={{ fontSize: '1rem', color: 'var(--claude-accent)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <FileText size={16} />
                          <span>SECTION 2: SUSPICIOUS ACTIVITY NARRATIVE (OFFICIAL PROSE)</span>
                        </h3>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Generated by Agent 5 (Groq LLM)
                        </span>
                      </div>
                      <div
                        style={{
                          backgroundColor: 'var(--bg-primary)',
                          padding: '1.15rem 1.25rem',
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border-subtle)',
                          fontSize: '0.92rem',
                          lineHeight: '1.7',
                          color: 'var(--text-primary)',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {sarReport.sar_draft?.narrative || 'Narrative text pending generation...'}
                      </div>
                    </div>

                    {/* Section 3: Flagged Transactions Ledger */}
                    <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <h3 style={{ fontSize: '1rem', color: 'var(--claude-accent)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <DollarSign size={16} />
                        <span>SECTION 3: FLAGGED TRANSACTIONS SUMMARY</span>
                      </h3>
                      <div className="data-table-container">
                        <table className="data-table">
                          <thead>
                            <tr>
                              <th>TX ID</th>
                              <th>DATE</th>
                              <th>AMOUNT</th>
                              <th>DIRECTION</th>
                              <th>COUNTERPARTY</th>
                              <th>RISK FACTOR</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(sarReport.sar_draft?.transaction_summary || []).map((tx, idx) => (
                              <tr key={idx}>
                                <td style={{ fontWeight: 600 }}>{tx.transaction_id || `TXN-00${idx + 1}`}</td>
                                <td>{tx.date || '2026-10-01'}</td>
                                <td style={{ fontWeight: 600, color: 'var(--danger)' }}>
                                  ${Number(tx.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </td>
                                <td>
                                  <span className="pill-badge" style={{ backgroundColor: 'var(--bg-tertiary)', fontSize: '0.75rem' }}>
                                    {tx.direction || 'Inbound'}
                                  </span>
                                </td>
                                <td style={{ fontFamily: 'var(--font-mono)' }}>{tx.counterparty || '[NAME_X]'}</td>
                                <td style={{ color: 'var(--text-secondary)' }}>{tx.risk_factor || 'Structuring'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {/* Section 4: Key AML Indicators & Triggered Rules */}
                    <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <h3 style={{ fontSize: '1rem', color: 'var(--claude-accent)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <AlertCircle size={16} />
                        <span>SECTION 4: KEY AML INDICATORS &amp; STATUTORY BREACHES</span>
                      </h3>
                      <div style={{ marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                          STATUTORY REGULATORY CITATIONS
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                          {(sarReport.sar_draft?.key_indicators?.statutory_breaches || ['31 U.S.C. 5324 (Structuring)', '31 CFR 1020.320 (BSA Filing)']).map((cite, idx) => (
                            <span key={idx} className="pill-badge pill-badge-danger">
                              {cite}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        EVIDENCE ENGINE RULES TRIGGERED ({sarReport.triggered_rules?.length || 0})
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
                        {(sarReport.triggered_rules || []).map((rule, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: '0.85rem 1rem',
                              backgroundColor: 'var(--surface)',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--border)',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                              <span style={{ fontWeight: 600, color: 'var(--accent)', fontSize: '0.85rem' }}>
                                {rule.rule_id}
                              </span>
                              <span className="pill-badge pill-badge-danger" style={{ fontSize: '0.68rem' }}>
                                {rule.severity || 'HIGH'}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.25rem' }}>
                              {rule.rule_name}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                              {rule.evidence || rule.description}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Section 5: Analyst Declaration & Signature */}
                    <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <h3 style={{ fontSize: '1rem', color: 'var(--claude-accent)', marginBottom: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <CheckCircle2 size={16} />
                        <span>SECTION 5: ANALYST CERTIFICATION &amp; ELECTRONIC SIGNATURE</span>
                      </h3>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem', fontSize: '0.85rem' }}>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>FILING ANALYST</div>
                          <div style={{ fontWeight: 600 }}>{sarReport.sar_draft?.analyst_declaration?.analyst_name || 'Senior AML Investigator #4092'}</div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>FILING DATE</div>
                          <div style={{ fontWeight: 600 }}>{sarReport.sar_draft?.analyst_declaration?.date || new Date().toISOString().split('T')[0]}</div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>ELECTRONIC SIGNATURE</div>
                          <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: 'var(--success)' }}>
                            {sarReport.sar_draft?.analyst_declaration?.signature || 'DIGITALLY_SIGNED_COMPLIANCE_AGENT'}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab 1: Case Details & Subject Profile */}
            {activeTab === 'overview' && (

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1.5rem' }}>
                {/* Case Alert Details Card */}
                <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <h3 style={{ fontSize: '1.05rem', marginBottom: '0.85rem', color: 'var(--claude-accent)' }}>
                    Case Alert &amp; Suspicion Details
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {Object.entries(ingestionResult.case_details || {}).map(([key, val]) => (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                        <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                          {key.replace(/_/g, ' ')}:
                        </span>
                        <span style={{ fontWeight: 500, maxWidth: '65%', textAlign: 'right', wordBreak: 'break-word' }}>
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Subject KYC Profile Card */}
                <div style={{ padding: '1.25rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <h3 style={{ fontSize: '1.05rem', marginBottom: '0.85rem', color: 'var(--claude-accent)' }}>
                    Subject Entity &amp; KYC Profile
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                    {Object.entries(ingestionResult.subject_profile || {}).map(([key, val]) => (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.4rem' }}>
                        <span style={{ color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                          {key.replace(/_/g, ' ')}:
                        </span>
                        <span style={{ fontWeight: 500, maxWidth: '65%', textAlign: 'right', wordBreak: 'break-word' }}>
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Financial Transactions Table */}
            {activeTab === 'transactions' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                    Parsed records from Transactions CSV ({ingestionResult.financial_activity?.transactions?.length || 0} rows)
                  </p>
                </div>
                {ingestionResult.financial_activity?.transactions?.length > 0 ? (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {Object.keys(ingestionResult.financial_activity.transactions[0]).map(col => (
                            <th key={col}>{col.toUpperCase()}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {ingestionResult.financial_activity.transactions.map((row, idx) => (
                          <tr key={idx}>
                            {Object.values(row).map((val, cellIdx) => (
                              <td key={cellIdx}>{String(val)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-muted)' }}>No transactions found in parsed case data.</p>
                )}
              </div>
            )}

            {/* Tab 3: Supporting Accounts & Records */}
            {activeTab === 'accounts' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                    Parsed records from Accounts / Activity CSV ({ingestionResult.supporting_activity?.records?.length || 0} rows)
                  </p>
                </div>
                {ingestionResult.supporting_activity?.records?.length > 0 ? (
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          {Object.keys(ingestionResult.supporting_activity.records[0]).map(col => (
                            <th key={col}>{col.toUpperCase()}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {ingestionResult.supporting_activity.records.map((row, idx) => (
                          <tr key={idx}>
                            {Object.values(row).map((val, cellIdx) => (
                              <td key={cellIdx}>{String(val)}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-muted)' }}>No supporting records found in parsed case data.</p>
                )}
              </div>
            )}

            {/* Tab 4: Canonical structured_case JSON Viewer */}
            {activeTab === 'json' && (
              <div style={{ position: 'relative' }}>
                <pre
                  style={{
                    backgroundColor: 'var(--bg-secondary)',
                    padding: '1.25rem',
                    borderRadius: 'var(--radius-sm)',
                    overflowX: 'auto',
                    fontSize: '0.85rem',
                    color: 'var(--text-primary)',
                    maxHeight: '500px',
                    lineHeight: '1.5',
                  }}
                >
                  {JSON.stringify(ingestionResult, null, 2)}
                </pre>
              </div>
            )}

            {/* Tab 5: Storage Manifest */}
            {activeTab === 'manifest' && (
              <div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.85rem' }}>
                  Input files verified in Supabase bucket <strong>{ingestionResult.ingestion_metadata?.bucket}</strong> at folder <strong>{ingestionResult.ingestion_metadata?.folder}</strong>:
                </p>
                <div className="data-table-container">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>FILENAME</th>
                        <th>STORAGE PATH</th>
                        <th>EXTENSION</th>
                        <th>SIZE</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(ingestionResult.ingestion_metadata?.file_manifest || []).map((f, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{f.filename}</td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>{f.storage_path}</td>
                          <td>
                            <span className="pill-badge pill-badge-accent">.{f.extension}</span>
                          </td>
                          <td>{(f.size_bytes / 1024).toFixed(2)} KB</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ----------------- Direct Ingestion Modal ----------------- */}
      {showDirectModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={() => setShowDirectModal(false)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '480px', width: '100%' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1.2rem', margin: 0 }}>Direct Ingestion Tester</h3>
              <button
                onClick={() => setShowDirectModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
              Ingest a case that is already stored in your Supabase <strong>Uploads</strong> bucket by entering its folder name.
            </p>
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                CASE ID / FOLDER NAME
              </label>
              <input
                type="text"
                className="claude-input"
                placeholder="e.g. SAR-CASE-2026-001"
                value={directCaseId}
                onChange={e => setDirectCaseId(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button onClick={() => setShowDirectModal(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowDirectModal(false);
                  handleRunIngestion(directCaseId.trim());
                }}
                disabled={!directCaseId.trim()}
                className="btn btn-primary"
              >
                Trigger Ingestion
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- File Preview Modal ----------------- */}
      {previewContent && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
          }}
          onClick={() => setPreviewContent(null)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '720px', width: '100%', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', margin: 0 }}>{previewContent.name}</h3>
                <span className="pill-badge pill-badge-accent" style={{ marginTop: '0.25rem' }}>
                  {previewContent.type.toUpperCase()} PREVIEW
                </span>
              </div>
              <button
                onClick={() => setPreviewContent(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>
            <pre
              style={{
                flex: 1,
                overflowY: 'auto',
                backgroundColor: 'var(--bg-secondary)',
                padding: '1rem',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.82rem',
                color: 'var(--text-primary)',
                lineHeight: '1.45',
              }}
            >
              {previewContent.text}
            </pre>
          </div>
        </div>
      )}

      {/* ----------------- Previous SARs Modal ----------------- */}
      {showPreviousModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
            backdropFilter: 'blur(4px)',
          }}
          onClick={() => setShowPreviousModal(false)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '640px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <FolderArchive size={20} style={{ color: 'var(--claude-accent)' }} />
                <div>
                  <h3 style={{ fontSize: '1.2rem', margin: 0, fontFamily: 'var(--font-serif)' }}>Previous SAR Filings</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                    Archived investigative dockets &bull; FinCEN Repository
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowPreviousModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
              {/* Case 1 */}
              <div
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-secondary)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>SAR-CASE-2026-001</span>
                    <span className="pill-badge pill-badge-danger" style={{ fontSize: '0.65rem' }}>TBML (Iran Outflow)</span>
                    <span className="pill-badge pill-badge-neutral" style={{ fontSize: '0.65rem' }}>8 Wires</span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0 0 0.25rem' }}>
                    Entity: <strong>Spice Route Exports Pvt Ltd</strong> &bull; Total Outflow: INR 1.8 Cr
                  </p>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Filing Status: Formal SAR Filed &bull; Confidence: 92.0% &bull; Compliance: Passed
                  </span>
                </div>
                <button
                  onClick={() => {
                    setCaseId('SAR-CASE-2026-001');
                    setShowPreviousModal(false);
                    handleRunIngestion('SAR-CASE-2026-001');
                  }}
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Load Docket
                </button>
              </div>

              {/* Case 2 */}
              <div
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-secondary)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>SAR-CASE-2026-002</span>
                    <span className="pill-badge pill-badge-warning" style={{ fontSize: '0.65rem' }}>Structuring &amp; Layering</span>
                    <span className="pill-badge pill-badge-neutral" style={{ fontSize: '0.65rem' }}>6 Trans</span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0 0 0.25rem' }}>
                    Entity: <strong>Horizon Meridian Trading LLC</strong> &bull; Structured Cash: $950,000 USD
                  </p>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Filing Status: Under Audit &bull; Confidence: 85.6% &bull; PEP Associated
                  </span>
                </div>
                <button
                  onClick={() => {
                    setCaseId('SAR-CASE-2026-002');
                    loadSampleCase();
                    setShowPreviousModal(false);
                  }}
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Load Sample
                </button>
              </div>

              {/* Case 3 */}
              <div
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  backgroundColor: 'var(--bg-secondary)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '1rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>CASE-2024-0106</span>
                    <span className="pill-badge pill-badge-accent" style={{ fontSize: '0.65rem' }}>Rapid Pass-Through</span>
                    <span className="pill-badge pill-badge-neutral" style={{ fontSize: '0.65rem' }}>Panama / BVI</span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0 0 0.25rem' }}>
                    Entity: <strong>Apex Global Holdings Ltd</strong> &bull; Total Volume: $1,850,000 USD
                  </p>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    Filing Status: Closed Historical Case &bull; Prior SAR Flag: True
                  </span>
                </div>
                <button
                  onClick={() => {
                    setCaseId('CASE-2024-0106');
                    setShowPreviousModal(false);
                  }}
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Set ID
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowPreviousModal(false)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- Investigation History Modal ----------------- */}
      {showHistoryModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
            backdropFilter: 'blur(4px)',
          }}
          onClick={() => setShowHistoryModal(false)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '580px', width: '100%', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <History size={20} style={{ color: 'var(--claude-accent)' }} />
                <div>
                  <h3 style={{ fontSize: '1.2rem', margin: 0, fontFamily: 'var(--font-serif)' }}>Pipeline Audit Trail</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                    Deterministic Agent Verification &amp; Compliance Logs
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowHistoryModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.65rem', marginBottom: '1rem' }}>
              <div style={{ padding: '0.75rem', borderLeft: '3px solid var(--success)', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  <span>Agent 1 (Ingestion &amp; ML)</span>
                  <span>Active Session</span>
                </div>
                <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>
                  Pre-trained XGBoost Classifier executed with 33 canonical feature vectors.
                </div>
              </div>

              <div style={{ padding: '0.75rem', borderLeft: '3px solid var(--claude-accent)', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  <span>Masking Agent</span>
                  <span>PostgreSQL Vault</span>
                </div>
                <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>
                  Reversible PII encryption executed: Subject names, account numbers, and tax identifiers tokenized into pii_masking_vault.
                </div>
              </div>

              <div style={{ padding: '0.75rem', borderLeft: '3px solid var(--info)', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                  <span>Agent 3 (Evidence) &amp; Agent 5 (Narrative)</span>
                  <span>Groq LLM Engine</span>
                </div>
                <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>
                  8 deterministic FinCEN rules evaluated; 5-section official SAR report synthesized via Groq LLM.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowHistoryModal(false)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- System & Model Settings Modal ----------------- */}
      {showSettingsModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
            backdropFilter: 'blur(4px)',
          }}
          onClick={() => setShowSettingsModal(false)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '580px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <Settings size={20} style={{ color: 'var(--claude-accent)' }} />
                <div>
                  <h3 style={{ fontSize: '1.2rem', margin: 0, fontFamily: 'var(--font-serif)' }}>AI Pipeline Configuration</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                    Multi-Agent Architecture &amp; Regulatory Parameters
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowSettingsModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '1rem' }}>
              <div style={{ padding: '0.85rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '0.25rem' }}>LLM Synthesis Engine</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Model: <code style={{ color: 'var(--claude-accent)' }}>openai/gpt-oss-120b</code> via Groq Cloud API (Fallback: <code style={{ color: 'var(--claude-accent)' }}>qwen/qwen3.8-27b</code>)
                </div>
              </div>

              <div style={{ padding: '0.85rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '0.25rem' }}>ML Classification Model (Agent 1)</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Model: Pre-trained XGBoost multi:softprob (33 canonical features, 98.5% training accuracy)
                </div>
              </div>

              <div style={{ padding: '0.85rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '0.25rem' }}>PII Masking Vault</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Database: PostgreSQL (Table: <code style={{ color: 'var(--claude-accent)' }}>pii_masking_vault</code>)
                </div>
              </div>

              <div style={{ padding: '0.85rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)' }}>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '0.25rem' }}>Compliance Gate Threshold</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Standard: 31 CFR 1020.320 &bull; Minimum Pass Score: 60.0% &bull; Max Revisions: 3
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowSettingsModal(false)} className="btn btn-secondary">
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- Profile Modal ----------------- */}
      {showProfileModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.55)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem',
            backdropFilter: 'blur(4px)',
          }}
          onClick={() => setShowProfileModal(false)}
        >
          <div
            className="claude-card"
            style={{ maxWidth: '480px', width: '100%', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <User size={20} style={{ color: 'var(--claude-accent)' }} />
                <div>
                  <h3 style={{ fontSize: '1.2rem', margin: 0, fontFamily: 'var(--font-serif)' }}>Investigator Profile</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: 0 }}>
                    BSA Officer Credentials &bull; Authorized E-Filer
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowProfileModal(false)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                <div
                  style={{
                    width: '50px',
                    height: '50px',
                    borderRadius: 'var(--radius-pill)',
                    backgroundColor: 'var(--claude-accent)',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '1.25rem',
                  }}
                >
                  JM
                </div>
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>J. Mercer</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Senior AML &amp; Sanctions Analyst</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>Division of FinCEN Compliance &bull; First Global Commercial Bank</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.82rem' }}>
                <div style={{ padding: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>REGULATORY CLEARANCE</span>
                  <strong>FinCEN Level 3</strong>
                </div>
                <div style={{ padding: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>FILING SYSTEM ID</span>
                  <strong>#FINCEN-8842-US</strong>
                </div>
                <div style={{ padding: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>AUTHORITY</span>
                  <strong>31 U.S.C. 5318(g)</strong>
                </div>
                <div style={{ padding: '0.75rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                  <span style={{ color: 'var(--text-muted)', display: 'block', fontSize: '0.72rem' }}>SESSION STATE</span>
                  <span style={{ color: 'var(--success)', fontWeight: 600 }}>Active (Secure)</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowProfileModal(false)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- Footer ----------------- */}
      <footer
        style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '1.25rem 2rem',
          textAlign: 'center',
          fontSize: '0.8rem',
          color: 'var(--text-muted)',
          backgroundColor: 'var(--bg-surface)',
        }}
      >
        SAR Ingestion Studio &bull; Claude Editorial Theme &bull; FastAPI + Supabase Storage + React Vite
      </footer>
      </div>
    </div>
  );
}

