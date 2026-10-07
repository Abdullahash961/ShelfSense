import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '../api/client';
import './CameraPanel.css';

/**
 * CameraPanel — Live camera feed, connection controls, and scheduler management.
 *
 * Shows:
 *  - Camera connection status with green/red dot
 *  - Connect / Disconnect buttons
 *  - Live MJPEG feed (or snapshot fallback)
 *  - Scheduler controls: Start / Stop / Trigger
 *  - Next-run countdown bar
 */
export default function CameraPanel({ onAnalysisComplete, showToast }) {
  const [camStatus, setCamStatus] = useState({ connected: false, source: null, resolution: null });
  const [schedStatus, setSchedStatus] = useState({
    running: false,
    interval_minutes: 5,
    last_run: null,
    last_status: 'never',
    next_run: null,
    cycle_count: 0,
  });
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState('');
  const [countdownPct, setCountdownPct] = useState(0);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay = useRef(1000);

  // ── Fetch status once on mount (before WS connects) ───────────────

  const refreshAll = useCallback(async () => {
    try {
      const [cam, sched] = await Promise.all([
        api.getCameraStatus(),
        api.getSchedulerStatus(),
      ]);
      setCamStatus(cam);
      setSchedStatus(sched);
    } catch {
      // silently ignore initial fetch errors
    }
  }, []);

  // ── WebSocket connection for real-time updates ────────────────────

  useEffect(() => {
    // Initial fetch as fallback
    refreshAll();

    const connectWs = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/ws/status`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        reconnectDelay.current = 1000; // reset backoff on successful connect
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'status_update') {
            if (msg.scheduler) setSchedStatus(msg.scheduler);
            if (msg.camera) setCamStatus(msg.camera);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Auto-reconnect with exponential backoff (max 30s)
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
          connectWs();
        }, reconnectDelay.current);
      };

      ws.onerror = () => {
        ws.close(); // trigger onclose → reconnect
      };

      wsRef.current = ws;
    };

    connectWs();

    return () => {
      // Cleanup on unmount
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [refreshAll]);

  // ── Countdown timer ───────────────────────────────────────────────

  useEffect(() => {
    if (!schedStatus.running || !schedStatus.next_run) {
      setCountdown('');
      setCountdownPct(0);
      return;
    }

    const tick = () => {
      const now = new Date();
      const next = new Date(schedStatus.next_run);
      const diff = Math.max(0, next - now);

      if (diff <= 0) {
        setCountdown('Running now...');
        setCountdownPct(100);
        return;
      }

      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setCountdown(`${mins}m ${secs}s`);

      // Calculate percentage elapsed
      const totalMs = schedStatus.interval_minutes * 60000;
      const elapsed = totalMs - diff;
      setCountdownPct(Math.min(100, (elapsed / totalMs) * 100));
    };

    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [schedStatus.running, schedStatus.next_run, schedStatus.interval_minutes]);

  // ── Actions ───────────────────────────────────────────────────────

  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await api.connectCamera(0);
      setCamStatus(res);
      showToast?.('Camera connected', 'success');
    } catch (err) {
      showToast?.(`Connection failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      const res = await api.disconnectCamera();
      setCamStatus(res);
      showToast?.('Camera disconnected', 'info');
    } catch (err) {
      showToast?.(`Disconnect failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleStartScheduler = async () => {
    setLoading(true);
    try {
      const res = await api.startScheduler();
      setSchedStatus(res);
      showToast?.('Scheduler started', 'success');
    } catch (err) {
      showToast?.(`Start failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleStopScheduler = async () => {
    setLoading(true);
    try {
      const res = await api.stopScheduler();
      setSchedStatus(res);
      showToast?.('Scheduler stopped', 'info');
    } catch (err) {
      showToast?.(`Stop failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleTrigger = async () => {
    setLoading(true);
    try {
      await api.triggerAnalysis();
      showToast?.('Analysis cycle triggered', 'success');
      onAnalysisComplete?.();
      refreshAll();
    } catch (err) {
      showToast?.(`Trigger failed: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────

  const formatTime = (isoStr) => {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const connected = camStatus.connected;

  return (
    <div className="camera-panel" id="camera-panel">
      <h2>
        <span className="icon">📷</span>
        Camera & Scheduler
      </h2>

      {/* ── Status Row ────────────────────────────────────────────── */}
      <div className="camera-status-row">
        <div className="status-indicator">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
        {connected && camStatus.source && (
          <span className="status-meta">
            Source: {camStatus.source}
            {camStatus.resolution && (
              <> &middot; {camStatus.resolution.width}×{camStatus.resolution.height}</>
            )}
          </span>
        )}
      </div>

      {/* ── Controls ──────────────────────────────────────────────── */}
      <div className="camera-controls">
        {!connected ? (
          <button
            className="btn-cam btn-connect"
            onClick={handleConnect}
            disabled={loading}
          >
            ⚡ Connect Camera
          </button>
        ) : (
          <button
            className="btn-cam btn-disconnect"
            onClick={handleDisconnect}
            disabled={loading}
          >
            ✕ Disconnect
          </button>
        )}

        <button
          className="btn-cam btn-trigger"
          onClick={handleTrigger}
          disabled={loading || !connected}
          title={!connected ? 'Connect camera first' : 'Run one analysis cycle now'}
        >
          ▶ Analyze Now
        </button>
      </div>

      {/* ── Live Feed / Snapshot ──────────────────────────────────── */}
      <div className="camera-feed-container">
        {connected ? (
          <>
            <div className="feed-badge">
              <span className="live-dot" />
              LIVE
            </div>
            <img
              src={api.getCameraFeedUrl()}
              alt="Live camera feed"
              onError={(e) => {
                // Fall back to a snapshot if MJPEG fails
                e.target.onerror = null;
                e.target.src = api.getSnapshotUrl();
              }}
            />
          </>
        ) : (
          <div className="feed-placeholder">
            <div className="placeholder-icon">📹</div>
            <div>Camera not connected</div>
            <div style={{ fontSize: '0.78rem', marginTop: '0.3rem', opacity: 0.7 }}>
              Click "Connect Camera" to start the live feed
            </div>
          </div>
        )}
      </div>

      {/* ── Scheduler Section ─────────────────────────────────────── */}
      <div className="scheduler-section">
        <h3>
          <span>⏱️</span> Auto-Analysis Scheduler
        </h3>

        <div className="scheduler-grid">
          <div className="scheduler-stat">
            <div className="stat-label">Status</div>
            <div className={`stat-value ${schedStatus.running ? 'running' : 'stopped'}`}>
              {schedStatus.running ? '● Running' : '○ Stopped'}
            </div>
          </div>
          <div className="scheduler-stat">
            <div className="stat-label">Interval</div>
            <div className="stat-value">
              {schedStatus.interval_minutes} min
            </div>
          </div>
          <div className="scheduler-stat">
            <div className="stat-label">Last Run</div>
            <div className="stat-value">{formatTime(schedStatus.last_run)}</div>
          </div>
          <div className="scheduler-stat">
            <div className="stat-label">Cycles</div>
            <div className="stat-value">{schedStatus.cycle_count}</div>
          </div>
        </div>

        {/* Scheduler controls */}
        <div className="camera-controls">
          {!schedStatus.running ? (
            <button
              className="btn-cam btn-connect"
              onClick={handleStartScheduler}
              disabled={loading || !connected}
              title={!connected ? 'Connect camera first' : 'Start periodic analysis'}
            >
              ▶ Start Scheduler
            </button>
          ) : (
            <button
              className="btn-cam btn-disconnect"
              onClick={handleStopScheduler}
              disabled={loading}
            >
              ■ Stop Scheduler
            </button>
          )}
        </div>

        {schedStatus.last_status && schedStatus.last_status !== 'never' && (
          <div className="status-meta" style={{ marginBottom: '0.75rem' }}>
            Last result: {schedStatus.last_status}
          </div>
        )}

        {/* Countdown bar */}
        {schedStatus.running && countdown && (
          <div className="countdown-bar">
            <div className="countdown-label">
              <span>Next analysis</span>
              <span>{countdown}</span>
            </div>
            <div className="countdown-track">
              <div
                className="countdown-fill"
                style={{ width: `${countdownPct}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
