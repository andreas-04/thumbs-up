import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../services/api';
import type {
  AuditLogEntry,
  AuditLogResponse,
  AuditLogStats,
  AuditLogFilters,
  SystemLogEntry,
  SystemLogResponse,
  AuditTab,
} from '../../services/api';

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

const ACTION_COLORS: Record<string, string> = {
  auth: 'text-term-blue',
  file: 'text-term-yellow',
  cert: 'text-term-purple',
  permission: 'text-term-cyan',
  user: 'text-term-green',
  group: 'text-term-green',
  domain: 'text-term-cyan',
  settings: 'text-term-dim',
};

function actionColor(action: string) {
  const prefix = action.split('.')[0];
  return ACTION_COLORS[prefix] ?? 'text-term-dim';
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString();
}

function truncateEmail(email: string | null, max = 22) {
  if (!email) return 'system';
  return email.length > max ? email.slice(0, max - 1) + '…' : email;
}

// ---------------------------------------------------------------------------
// Tab config
// ---------------------------------------------------------------------------

const TABS: { key: AuditTab; label: string }[] = [
  { key: 'all', label: 'ALL' },
  { key: 'files', label: 'FILES' },
  { key: 'security', label: 'SECURITY' },
  { key: 'system', label: 'SYSTEM' },
];

const POLL_INTERVAL = 5000;

// ---------------------------------------------------------------------------
// TerminalPane — renders audit log entries
// ---------------------------------------------------------------------------

interface TerminalPaneProps {
  entries: AuditLogEntry[];
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  isLive: boolean;
}

function TerminalPane({ entries, loading, hasMore, onLoadMore, isLive }: TerminalPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showNewPill, setShowNewPill] = useState(false);
  const prevCountRef = useRef(entries.length);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    } else if (entries.length > prevCountRef.current) {
      setShowNewPill(true);
    }
    prevCountRef.current = entries.length;
  }, [entries.length, autoScroll]);

  // Detect user scrolling away from bottom
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setAutoScroll(atBottom);
    if (atBottom) setShowNewPill(false);

    // Load more when scrolled near top
    if (el.scrollTop < 40 && hasMore && !loading) {
      onLoadMore();
    }
  }, [hasMore, loading, onLoadMore]);

  const snapToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    setAutoScroll(true);
    setShowNewPill(false);
  };

  return (
    <div className="relative flex-1 min-h-0">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto p-3 text-xs leading-5 bg-[#0a0a0f] scanlines"
      >
        {loading && entries.length === 0 && (
          <div className="text-term-dim">loading audit log...</div>
        )}
        {hasMore && (
          <button
            onClick={onLoadMore}
            disabled={loading}
            className="text-term-dim hover:text-foreground text-xs mb-2 block"
          >
            {loading ? '↑ loading history...' : '↑ load older entries'}
          </button>
        )}
        {entries.map((e) => (
          <div key={e.id} className="flex gap-2 whitespace-nowrap hover:bg-glass-highlight transition-colors">
            <span className="text-term-dim" title={formatDate(e.timestamp)}>
              [{formatTime(e.timestamp)}]
            </span>
            <span className={`${actionColor(e.action)} uppercase w-12 text-right shrink-0`}>
              {e.action.split('.')[0]}
            </span>
            <span className="text-foreground w-44 shrink-0 overflow-hidden text-ellipsis" title={e.userEmail ?? undefined}>
              {truncateEmail(e.userEmail)}
            </span>
            <span className="text-term-dim">→</span>
            <span className="text-foreground flex-1 overflow-hidden text-ellipsis">
              {e.description ?? e.action}
            </span>
            <span className={e.status === 'success' ? 'text-term-green' : 'text-term-red animate-pulse'}>
              {e.status.toUpperCase()}
            </span>
          </div>
        ))}
        {isLive && autoScroll && (
          <span className="text-term-green animate-[blink_1s_step-end_infinite]">█</span>
        )}
        <div ref={bottomRef} />
      </div>

      {showNewPill && (
        <button
          onClick={snapToBottom}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 text-xs rounded-full bg-glass-highlight border border-glass-border text-term-green hover:bg-glass-border transition-colors"
        >
          ↓ New entries
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SystemLogPane — renders Docker container logs
// ---------------------------------------------------------------------------

interface SystemLogPaneProps {
  container: string;
  onContainerChange: (c: string) => void;
  tail: number;
  onTailChange: (t: number) => void;
  grep: string;
  onGrepChange: (g: string) => void;
  logs: SystemLogEntry[];
  loading: boolean;
  available: boolean;
  isLive: boolean;
}

const LEVEL_COLORS: Record<string, string> = {
  error: 'text-term-red',
  warning: 'text-term-yellow',
  info: 'text-term-blue',
  debug: 'text-term-dim',
};

function detectLevel(line: string): string {
  const upper = line.toUpperCase();
  if (upper.includes('ERROR')) return 'error';
  if (upper.includes('WARNING') || upper.includes('WARN')) return 'warning';
  if (upper.includes('DEBUG')) return 'debug';
  return 'info';
}

function SystemLogPane({
  container,
  onContainerChange,
  tail,
  onTailChange,
  grep,
  onGrepChange,
  logs,
  loading,
  available,
  isLive,
}: SystemLogPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const filtered = grep
    ? logs.filter((l) => l.line.toLowerCase().includes(grep.toLowerCase()))
    : logs;

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filtered.length, autoScroll]);

  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setAutoScroll(atBottom);
  }, []);

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* System filter bar */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-glass-border text-xs">
        <span className="text-term-green">$</span>
        <span className="text-term-dim">logs</span>

        <span className="text-term-dim">--container=</span>
        <div className="flex gap-1">
          {['thumbsup-backend', 'thumbsup-frontend'].map((c) => (
            <button
              key={c}
              onClick={() => onContainerChange(c)}
              className={`px-2 py-0.5 rounded text-xs border transition-colors ${
                container === c
                  ? 'border-term-green text-term-green bg-glass-highlight'
                  : 'border-glass-border text-term-dim hover:text-foreground'
              }`}
            >
              {c.replace('thumbsup-', '')}
            </button>
          ))}
        </div>

        <span className="text-term-dim">--grep=</span>
        <input
          value={grep}
          onChange={(e) => onGrepChange(e.target.value)}
          placeholder="filter..."
          className="bg-transparent border border-glass-border rounded px-2 py-0.5 text-foreground text-xs w-32 focus:border-term-green focus:outline-none transition-colors"
        />

        <span className="text-term-dim">--tail=</span>
        <select
          value={tail}
          onChange={(e) => onTailChange(Number(e.target.value))}
          className="bg-transparent border border-glass-border rounded px-1 py-0.5 text-foreground text-xs focus:border-term-green focus:outline-none"
        >
          {[100, 200, 500, 1000].map((n) => (
            <option key={n} value={n} className="bg-[#0a0a0f]">
              {n}
            </option>
          ))}
        </select>
      </div>

      {/* Log output */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3 text-xs leading-5 bg-[#0a0a0f] scanlines"
      >
        {!available && (
          <div className="text-term-yellow">
            [system] Docker socket unavailable. Mount /var/run/docker.sock to enable system logs.
          </div>
        )}
        {loading && logs.length === 0 && available && (
          <div className="text-term-dim">loading container logs...</div>
        )}
        {filtered.map((l, i) => {
          const level = detectLevel(l.line);
          return (
            <div key={i} className="flex gap-2 whitespace-nowrap hover:bg-glass-highlight transition-colors">
              {l.timestamp && (
                <span className="text-term-dim">[{formatTime(l.timestamp)}]</span>
              )}
              <span className={`${LEVEL_COLORS[level]} uppercase w-10 text-right shrink-0`}>
                {level}
              </span>
              <span className="text-foreground flex-1 overflow-hidden text-ellipsis whitespace-pre">
                {l.line}
              </span>
            </div>
          );
        })}
        {isLive && autoScroll && available && (
          <span className="text-term-green animate-[blink_1s_step-end_infinite]">█</span>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterBar — command-prompt style filters for audit tabs
// ---------------------------------------------------------------------------

interface FilterBarProps {
  filters: AuditLogFilters;
  onChange: (f: AuditLogFilters) => void;
  showActionFilter: boolean;
}

function FilterBar({ filters, onChange, showActionFilter }: FilterBarProps) {
  const [searchDraft, setSearchDraft] = useState(filters.search ?? '');
  const [userDraft, setUserDraft] = useState(filters.userEmail ?? '');
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const debounceUpdate = useCallback(
    (key: 'search' | 'userEmail', value: string) => {
      clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        onChange({ ...filters, [key]: value || undefined, page: 1 });
      }, 300);
    },
    [filters, onChange],
  );

  const hasActiveFilters = filters.status || filters.userEmail || filters.search || filters.action;

  return (
    <div className="flex items-center gap-3 px-3 py-2 border-b border-glass-border text-xs flex-wrap">
      <span className="text-term-green">$</span>
      <span className="text-term-dim">filter</span>

      {showActionFilter && (
        <>
          <span className="text-term-dim">--action=</span>
          <select
            value={filters.action ?? ''}
            onChange={(e) => onChange({ ...filters, action: e.target.value || undefined, page: 1 })}
            className="bg-transparent border border-glass-border rounded px-1 py-0.5 text-foreground text-xs focus:border-term-green focus:outline-none"
          >
            <option value="" className="bg-[#0a0a0f]">all</option>
            <option value="auth" className="bg-[#0a0a0f]">auth</option>
            <option value="file" className="bg-[#0a0a0f]">file</option>
            <option value="cert" className="bg-[#0a0a0f]">cert</option>
            <option value="user" className="bg-[#0a0a0f]">user</option>
            <option value="group" className="bg-[#0a0a0f]">group</option>
            <option value="permission" className="bg-[#0a0a0f]">permission</option>
            <option value="domain" className="bg-[#0a0a0f]">domain</option>
            <option value="settings" className="bg-[#0a0a0f]">settings</option>
          </select>
        </>
      )}

      <span className="text-term-dim">--user=</span>
      <input
        value={userDraft}
        onChange={(e) => {
          setUserDraft(e.target.value);
          debounceUpdate('userEmail', e.target.value);
        }}
        placeholder="email..."
        className="bg-transparent border border-glass-border rounded px-2 py-0.5 text-foreground text-xs w-32 focus:border-term-green focus:outline-none transition-colors"
      />

      <span className="text-term-dim">--status=</span>
      <select
        value={filters.status ?? ''}
        onChange={(e) => onChange({ ...filters, status: e.target.value || undefined, page: 1 })}
        className="bg-transparent border border-glass-border rounded px-1 py-0.5 text-foreground text-xs focus:border-term-green focus:outline-none"
      >
        <option value="" className="bg-[#0a0a0f]">all</option>
        <option value="success" className="bg-[#0a0a0f]">success</option>
        <option value="failure" className="bg-[#0a0a0f]">failure</option>
      </select>

      <span className="text-term-dim">--search=</span>
      <input
        value={searchDraft}
        onChange={(e) => {
          setSearchDraft(e.target.value);
          debounceUpdate('search', e.target.value);
        }}
        placeholder="description..."
        className="bg-transparent border border-glass-border rounded px-2 py-0.5 text-foreground text-xs w-36 focus:border-term-green focus:outline-none transition-colors"
      />

      {hasActiveFilters && (
        <button
          onClick={() => {
            setSearchDraft('');
            setUserDraft('');
            onChange({ page: 1 });
          }}
          className="text-term-red hover:text-term-red/80 text-xs transition-colors"
        >
          [x] clear
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AuditLog page
// ---------------------------------------------------------------------------

interface TabState {
  entries: AuditLogEntry[];
  total: number;
  page: number;
  pages: number;
  filters: AuditLogFilters;
  loading: boolean;
  initialized: boolean;
}

function initialTabState(category?: string): TabState {
  return {
    entries: [],
    total: 0,
    page: 1,
    pages: 1,
    filters: category ? { category, page: 1, perPage: 100 } : { page: 1, perPage: 100 },
    loading: false,
    initialized: false,
  };
}

export default function AuditLog() {
  const [activeTab, setActiveTab] = useState<AuditTab>('all');
  const [stats, setStats] = useState<AuditLogStats | null>(null);
  const [isLive, setIsLive] = useState(true);

  // Per-tab state
  const [allState, setAllState] = useState<TabState>(initialTabState());
  const [filesState, setFilesState] = useState<TabState>(initialTabState('files'));
  const [securityState, setSecurityState] = useState<TabState>(initialTabState('security'));

  // System tab state
  const [sysContainer, setSysContainer] = useState('thumbsup-backend');
  const [sysTail, setSysTail] = useState(200);
  const [sysGrep, setSysGrep] = useState('');
  const [sysLogs, setSysLogs] = useState<SystemLogEntry[]>([]);
  const [sysAvailable, setSysAvailable] = useState(true);
  const [sysLoading, setSysLoading] = useState(false);
  const [sysInitialized, setSysInitialized] = useState(false);

  const tabStateMap: Record<Exclude<AuditTab, 'system'>, [TabState, React.Dispatch<React.SetStateAction<TabState>>]> = {
    all: [allState, setAllState],
    files: [filesState, setFilesState],
    security: [securityState, setSecurityState],
  };

  // Fetch audit log entries for a tab
  const fetchAuditTab = useCallback(
    async (
      tab: Exclude<AuditTab, 'system'>,
      opts?: { append?: boolean; prepend?: boolean },
    ) => {
      const [state, setState] = tabStateMap[tab];
      setState((s) => ({ ...s, loading: true }));

      try {
        const res: AuditLogResponse = await api.getAuditLogs(state.filters);
        setState((s) => {
          // Reverse so oldest is at top (API returns newest first)
          const newEntries = [...res.logs].reverse();
          let entries: AuditLogEntry[];
          if (opts?.prepend) {
            // Prepend older entries (history loading)
            const existingIds = new Set(s.entries.map((e) => e.id));
            const unique = newEntries.filter((e) => !existingIds.has(e.id));
            entries = [...unique, ...s.entries];
          } else if (opts?.append) {
            // Append newer entries (polling)
            const existingIds = new Set(s.entries.map((e) => e.id));
            const unique = newEntries.filter((e) => !existingIds.has(e.id));
            entries = [...s.entries, ...unique];
          } else {
            entries = newEntries;
          }
          return {
            ...s,
            entries,
            total: res.total,
            page: res.page,
            pages: res.pages,
            loading: false,
            initialized: true,
          };
        });
      } catch {
        setState((s) => ({ ...s, loading: false, initialized: true }));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allState.filters, filesState.filters, securityState.filters],
  );

  // Fetch system logs
  const fetchSystemLogs = useCallback(async () => {
    setSysLoading(true);
    try {
      const res: SystemLogResponse = await api.getSystemLogs(sysContainer, sysTail);
      setSysLogs(res.logs);
      setSysAvailable(res.available);
      setSysInitialized(true);
    } catch {
      setSysAvailable(false);
      setSysInitialized(true);
    }
    setSysLoading(false);
  }, [sysContainer, sysTail]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const s = await api.getAuditLogStats();
      setStats(s);
    } catch {
      // ignore
    }
  }, []);

  // Initial load for active tab
  useEffect(() => {
    if (activeTab === 'system') {
      if (!sysInitialized) fetchSystemLogs();
    } else {
      const [state] = tabStateMap[activeTab];
      if (!state.initialized) fetchAuditTab(activeTab);
    }
    fetchStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // Polling
  useEffect(() => {
    if (!isLive) return;

    const interval = setInterval(() => {
      if (activeTab === 'system') {
        fetchSystemLogs();
      } else {
        const [state] = tabStateMap[activeTab];
        // Poll with since = latest timestamp
        if (state.entries.length > 0) {
          const latest = state.entries[state.entries.length - 1];
          const [, setState] = tabStateMap[activeTab];
          // Temporarily set filters with since for polling, then reset
          const pollFilters: AuditLogFilters = {
            ...state.filters,
            since: latest.timestamp,
            page: 1,
            perPage: 100,
          };
          api
            .getAuditLogs(pollFilters)
            .then((res) => {
              if (res.logs.length > 0) {
                const newEntries = [...res.logs].reverse();
                setState((s) => {
                  const existingIds = new Set(s.entries.map((e) => e.id));
                  const unique = newEntries.filter((e) => !existingIds.has(e.id));
                  return unique.length > 0
                    ? { ...s, entries: [...s.entries, ...unique], total: res.total }
                    : s;
                });
              }
            })
            .catch(() => {});
        }
        fetchStats();
      }
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLive, activeTab, sysContainer, sysTail, allState.entries.length, filesState.entries.length, securityState.entries.length]);

  // Re-fetch when filters change
  const handleFilterChange = (tab: Exclude<AuditTab, 'system'>, filters: AuditLogFilters) => {
    const [state, setState] = tabStateMap[tab];
    const category = state.filters.category;
    setState((s) => ({
      ...s,
      filters: { ...filters, category },
      entries: [],
      initialized: false,
    }));
  };

  // Trigger fetch after filter state update
  useEffect(() => {
    if (activeTab !== 'system') {
      const [state] = tabStateMap[activeTab];
      if (!state.initialized && !state.loading) {
        fetchAuditTab(activeTab);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allState.initialized, filesState.initialized, securityState.initialized]);

  // Re-fetch system logs when container or tail changes
  useEffect(() => {
    if (activeTab === 'system' && sysInitialized) {
      fetchSystemLogs();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sysContainer, sysTail]);

  // Load more (history)
  const loadMore = (tab: Exclude<AuditTab, 'system'>) => {
    const [state, setState] = tabStateMap[tab];
    if (state.page >= state.pages) return;
    setState((s) => ({
      ...s,
      filters: { ...s.filters, page: (s.filters.page ?? 1) + 1 },
    }));
    fetchAuditTab(tab, { prepend: true });
  };

  // Render current tab
  const renderTabContent = () => {
    if (activeTab === 'system') {
      return (
        <SystemLogPane
          container={sysContainer}
          onContainerChange={setSysContainer}
          tail={sysTail}
          onTailChange={setSysTail}
          grep={sysGrep}
          onGrepChange={setSysGrep}
          logs={sysLogs}
          loading={sysLoading}
          available={sysAvailable}
          isLive={isLive}
        />
      );
    }

    const [state] = tabStateMap[activeTab];
    return (
      <>
        <FilterBar
          filters={state.filters}
          onChange={(f) => handleFilterChange(activeTab, f)}
          showActionFilter={activeTab === 'all'}
        />
        <TerminalPane
          entries={state.entries}
          loading={state.loading}
          hasMore={state.page < state.pages}
          onLoadMore={() => loadMore(activeTab)}
          isLive={isLive}
        />
      </>
    );
  };

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-medium text-foreground">audit log</h1>
        <p className="text-muted-foreground text-xs mt-0.5">system event monitor</p>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="glass rounded flex items-center gap-6 px-4 py-2 text-xs">
          <div>
            <span className="text-term-dim">total </span>
            <span className="text-foreground">{stats.total.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-term-dim">today </span>
            <span className="text-foreground">{stats.today}</span>
          </div>
          <div>
            <span className="text-term-dim">failed auth </span>
            <span className={stats.failedAuthToday > 0 ? 'text-term-red' : 'text-foreground'}>
              {stats.failedAuthToday}
            </span>
          </div>
          <div>
            <span className="text-term-dim">active users </span>
            <span className="text-foreground">{stats.activeUsersToday}</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setIsLive(!isLive)}
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded border text-xs transition-colors ${
                isLive
                  ? 'border-term-green/30 text-term-green'
                  : 'border-glass-border text-term-dim hover:text-foreground'
              }`}
            >
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  isLive ? 'bg-term-green animate-pulse' : 'bg-term-dim'
                }`}
              />
              {isLive ? 'Live' : 'Paused'}
            </button>
          </div>
        </div>
      )}

      {/* Terminal window */}
      <div className="flex-1 min-h-0 flex flex-col rounded border border-glass-border overflow-hidden shadow-[0_0_15px_rgba(74,222,128,0.05)]">
        {/* Window chrome */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-glass-border bg-glass-bg">
          <span className="w-2.5 h-2.5 rounded-full bg-term-red/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-term-yellow/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-term-green/60" />
          <span className="text-term-dim text-xs ml-2">thumbsup audit-log</span>
          {stats && (
            <span className="text-term-dim text-xs ml-auto">
              ─── {stats.total.toLocaleString()} entries ───
            </span>
          )}
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-glass-border bg-glass-bg">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-4 py-1.5 text-xs font-medium transition-colors border-b-2 ${
                activeTab === t.key
                  ? 'text-term-green border-term-green bg-glass-highlight'
                  : 'text-term-dim border-transparent hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {renderTabContent()}
      </div>
    </div>
  );
}
