import { useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { AlertTriangle, Database, RefreshCw, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RISK_STYLES = {
  high: "bg-red-100 text-red-800 border-red-300",
  medium: "bg-yellow-100 text-yellow-900 border-yellow-300",
  low: "bg-green-100 text-green-800 border-green-300",
  unknown: "bg-zinc-100 text-zinc-700 border-zinc-300",
};

function RiskBadge({ level, testId }) {
  const cls = RISK_STYLES[level] || RISK_STYLES.unknown;
  return (
    <span
      data-testid={testId}
      className={`inline-block px-2 py-0.5 text-xs font-medium uppercase tracking-[0.1em] border ${cls}`}
    >
      {level || "unknown"}
    </span>
  );
}

function MetricCell({ label, value, testId, mono = true }) {
  return (
    <div className="border border-zinc-200 p-6 bg-white">
      <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-3">
        {label}
      </div>
      <div
        data-testid={testId}
        className={`text-4xl font-light tracking-tighter text-zinc-950 ${
          mono ? "font-mono" : ""
        }`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}

function formatNum(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString("en-US");
}

export default function AdminNameCollision() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [gender, setGender] = useState("unspecified");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [importing, setImporting] = useState(false);

  const loadStats = async () => {
    try {
      const r = await axios.get(`${API}/name-collision/stats`);
      setStats(r.data);
      return r.data;
    } catch (e) {
      console.error(e);
      return null;
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  // Poll stats while import is running
  useEffect(() => {
    if (!stats?.import_running) return;
    const id = setInterval(async () => {
      const s = await loadStats();
      if (s && !s.import_running) {
        clearInterval(id);
        setImporting(false);
        toast.success("Data import complete");
      }
    }, 4000);
    return () => clearInterval(id);
  }, [stats?.import_running]);

  const onCalculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const body = {
        first_name: firstName,
        last_name: lastName,
        gender: gender === "unspecified" ? null : gender,
      };
      const r = await axios.post(`${API}/name-collision/estimate`, body);
      setResult(r.data);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message;
      toast.error(`Calculation failed: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const onImport = async () => {
    setImporting(true);
    try {
      const r = await axios.post(`${API}/name-collision/import`);
      toast.info(`Import ${r.data.status}`);
      await loadStats();
    } catch (e) {
      toast.error(`Import failed: ${e.message}`);
      setImporting(false);
    }
  };

  const datasetReady = stats && stats.loaded && stats.first_name_count > 0;

  return (
    <div className="min-h-screen bg-white text-zinc-950 font-sans">
      <Toaster position="top-right" />

      {/* Header */}
      <header className="border-b border-zinc-200">
        <div className="px-6 md:px-12 py-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-2 h-8 bg-zinc-950" />
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">
                Internal Admin
              </div>
              <h1 className="text-xl font-semibold tracking-tight">
                Name Collision & Rarity Scoring
              </h1>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-6 text-xs font-mono text-zinc-500">
            <span>v1.0</span>
            <span>/admin/name-collision</span>
          </div>
        </div>
      </header>

      <main className="px-6 md:px-12 py-8 max-w-7xl mx-auto space-y-10">
        {/* Dataset status row */}
        <section
          data-testid="dataset-status-section"
          className="grid grid-cols-1 md:grid-cols-4 border border-zinc-200"
        >
          <div className="p-6 border-b md:border-b-0 md:border-r border-zinc-200">
            <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2 flex items-center gap-2">
              <Database className="w-3.5 h-3.5" /> First names
            </div>
            <div
              data-testid="first-name-count"
              className="text-3xl font-light font-mono tracking-tighter"
            >
              {formatNum(stats?.first_name_count)}
            </div>
          </div>
          <div className="p-6 border-b md:border-b-0 md:border-r border-zinc-200">
            <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2 flex items-center gap-2">
              <Database className="w-3.5 h-3.5" /> Last names
            </div>
            <div
              data-testid="last-name-count"
              className="text-3xl font-light font-mono tracking-tighter"
            >
              {formatNum(stats?.last_name_count)}
            </div>
          </div>
          <div className="p-6 border-b md:border-b-0 md:border-r border-zinc-200">
            <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
              Imported
            </div>
            <div
              data-testid="import-timestamp"
              className="text-sm font-mono text-zinc-900 break-all"
            >
              {stats?.meta?.imported_at || "—"}
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              SSA years:{" "}
              {stats?.meta?.ssa_year_min && stats?.meta?.ssa_year_max
                ? `${stats.meta.ssa_year_min}–${stats.meta.ssa_year_max}`
                : "—"}
            </div>
          </div>
          <div className="p-6 flex flex-col items-start justify-between">
            <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-3">
              Status
            </div>
            <div className="flex items-center gap-3 mb-4">
              {stats?.import_running || importing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin text-zinc-700" />
                  <span
                    data-testid="import-status"
                    className="text-sm text-zinc-700"
                  >
                    Import running…
                  </span>
                </>
              ) : datasetReady ? (
                <>
                  <div className="w-2 h-2 bg-green-600" />
                  <span
                    data-testid="import-status"
                    className="text-sm text-zinc-900"
                  >
                    Ready
                  </span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 bg-zinc-400" />
                  <span
                    data-testid="import-status"
                    className="text-sm text-zinc-700"
                  >
                    Not loaded
                  </span>
                </>
              )}
            </div>
            <Button
              data-testid="import-data-button"
              onClick={onImport}
              disabled={importing || stats?.import_running}
              variant="outline"
              className="rounded-none border-zinc-300 text-xs uppercase tracking-[0.1em]"
            >
              <RefreshCw className="w-3 h-3 mr-2" />
              Import / Refresh
            </Button>
          </div>
        </section>

        {/* Form */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <div className="lg:col-span-5 border border-zinc-200 p-6 md:p-8">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">
              01 — Input
            </div>
            <h2 className="text-2xl tracking-tight font-semibold mb-6">
              Calculate collision
            </h2>

            <div className="space-y-5">
              <div>
                <Label
                  htmlFor="first-name-input"
                  className="text-xs uppercase tracking-[0.12em] text-zinc-600 mb-2 block"
                >
                  First name
                </Label>
                <Input
                  id="first-name-input"
                  data-testid="first-name-input"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Daniel"
                  className="rounded-none border-zinc-300 focus-visible:ring-zinc-950"
                />
              </div>

              <div>
                <Label
                  htmlFor="last-name-input"
                  className="text-xs uppercase tracking-[0.12em] text-zinc-600 mb-2 block"
                >
                  Last name
                </Label>
                <Input
                  id="last-name-input"
                  data-testid="last-name-input"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Norris"
                  className="rounded-none border-zinc-300 focus-visible:ring-zinc-950"
                />
              </div>

              <div>
                <Label className="text-xs uppercase tracking-[0.12em] text-zinc-600 mb-2 block">
                  Gender (optional)
                </Label>
                <Select value={gender} onValueChange={setGender}>
                  <SelectTrigger
                    data-testid="gender-select"
                    className="rounded-none border-zinc-300 focus:ring-zinc-950"
                  >
                    <SelectValue placeholder="Auto-detect" />
                  </SelectTrigger>
                  <SelectContent className="rounded-none">
                    <SelectItem value="unspecified">
                      Auto-detect (dominant)
                    </SelectItem>
                    <SelectItem value="M">Male</SelectItem>
                    <SelectItem value="F">Female</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                data-testid="calculate-button"
                onClick={onCalculate}
                disabled={loading || !datasetReady}
                className="w-full rounded-none bg-zinc-950 hover:bg-zinc-800 text-white text-xs uppercase tracking-[0.15em] py-6"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Calculating…
                  </>
                ) : (
                  "Calculate"
                )}
              </Button>

              {!datasetReady && (
                <div className="text-xs text-zinc-500 flex items-start gap-2 border border-zinc-200 p-3">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>
                    Datasets are not loaded yet. Run{" "}
                    <strong>Import / Refresh</strong> first. The first import
                    takes 1–3 minutes.
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Results */}
          <div className="lg:col-span-7 space-y-6">
            <div>
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">
                02 — Result
              </div>
              <h2 className="text-2xl tracking-tight font-semibold">
                Collision estimate
              </h2>
            </div>

            {!result ? (
              <div className="border border-dashed border-zinc-300 p-12 text-center text-sm text-zinc-500">
                No calculation yet.
              </div>
            ) : (
              <ResultPanel result={result} />
            )}
          </div>
        </section>

        <footer className="pt-8 border-t border-zinc-200 text-xs text-zinc-500 space-y-2">
          <p>
            Sources: SSA Baby Names (birth-year window configurable) · U.S.
            Census 2010 Surnames.
          </p>
          <p>
            Formula:{" "}
            <span className="font-mono text-zinc-700">
              estimated_us_matches = (first_name_population *
              last_name_population) / 330,000,000
            </span>
          </p>
          <p className="italic max-w-3xl">
            estimated_us_matches is a statistical estimate based on independent
            first-name and last-name frequency. It should be used as a
            collision-risk signal, not an exact population count.
          </p>
        </footer>
      </main>
    </div>
  );
}

function ResultPanel({ result }) {
  const {
    first_name,
    last_name,
    first_name_normalized,
    last_name_normalized,
    gender_used,
    gender_confidence,
    first_name_population,
    first_name_risk_level,
    last_name_population,
    last_name_rank,
    last_name_risk_level,
    estimated_us_matches,
    full_name_collision_risk,
    confidence_penalty,
    rarity,
    nickname_canonical,
    alternate_estimate_for_canonical,
    hyphenated_last_name_parts,
    warnings = [],
    data_sources = [],
  } = result;

  return (
    <div data-testid="result-panel" className="space-y-6">
      {/* Headline */}
      <div className="border border-zinc-200 p-8">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="text-xs uppercase tracking-[0.15em] text-zinc-500">
              Estimated U.S. matches
            </div>
            <div
              data-testid="estimated-matches-metric"
              className="text-6xl font-light font-mono tracking-tighter text-zinc-950 mt-2"
            >
              {estimated_us_matches === null || estimated_us_matches === undefined
                ? "—"
                : formatNum(estimated_us_matches)}
            </div>
            <div className="mt-3 text-sm text-zinc-600">
              for{" "}
              <span className="font-mono text-zinc-900">
                {first_name} {last_name}
              </span>
              {first_name_normalized && last_name_normalized && (
                <span className="text-zinc-400">
                  {" "}
                  ({first_name_normalized} {last_name_normalized})
                </span>
              )}
            </div>
          </div>
          <div className="text-right space-y-3">
            <div>
              <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
                Full-name risk
              </div>
              <RiskBadge
                level={full_name_collision_risk}
                testId="risk-level-badge"
              />
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-1">
                Confidence penalty
              </div>
              <div
                data-testid="confidence-penalty-metric"
                className="text-2xl font-mono font-light tracking-tight"
              >
                {confidence_penalty?.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Rarity */}
      {rarity && (
        <RarityPanel rarity={rarity} estimate={estimated_us_matches} />
      )}

      {/* Metrics grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border border-zinc-200 [&>*:nth-child(odd)]:md:border-r [&>*:not(:last-child)]:border-b [&>*:nth-child(odd):last-child]:md:border-b-0 [&>*]:border-zinc-200">
        <div className="p-6">
          <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
            First-name population
          </div>
          <div
            data-testid="first-name-pop-metric"
            className="text-3xl font-light font-mono tracking-tighter"
          >
            {formatNum(first_name_population)}
          </div>
          <div className="mt-3 flex items-center gap-3 text-xs text-zinc-600">
            <RiskBadge level={first_name_risk_level} testId="first-name-risk-badge" />
            {gender_used && (
              <span className="font-mono">
                gender: {gender_used}
                {gender_confidence != null && (
                  <> · conf {Number(gender_confidence).toFixed(3)}</>
                )}
              </span>
            )}
          </div>
        </div>
        <div className="p-6">
          <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
            Last-name population
          </div>
          <div
            data-testid="last-name-pop-metric"
            className="text-3xl font-light font-mono tracking-tighter"
          >
            {formatNum(last_name_population)}
          </div>
          <div className="mt-3 flex items-center gap-3 text-xs text-zinc-600">
            <RiskBadge level={last_name_risk_level} testId="last-name-risk-badge" />
            {last_name_rank != null && (
              <span className="font-mono">rank #{formatNum(last_name_rank)}</span>
            )}
          </div>
        </div>
      </div>

      {/* Nickname */}
      {nickname_canonical && (
        <div
          data-testid="nickname-panel"
          className="border border-zinc-200 bg-zinc-50 p-6"
        >
          <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-2">
            Nickname detected
          </div>
          <div className="text-sm text-zinc-800 font-mono">
            {first_name_normalized} → {nickname_canonical}
          </div>
          {alternate_estimate_for_canonical && (
            <div className="mt-4 text-sm">
              <div className="text-xs uppercase tracking-[0.12em] text-zinc-500 mb-1">
                Alternate estimate for canonical form
              </div>
              <div className="font-mono">
                {nickname_canonical} {last_name} →{" "}
                <span className="text-zinc-950 font-medium">
                  {formatNum(
                    alternate_estimate_for_canonical.estimated_us_matches
                  )}
                </span>{" "}
                <RiskBadge
                  level={alternate_estimate_for_canonical.full_name_collision_risk}
                  testId="canonical-risk-badge"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Hyphenated breakdown */}
      {hyphenated_last_name_parts && (
        <div className="border border-zinc-200 p-6">
          <div className="text-xs uppercase tracking-[0.15em] text-zinc-500 mb-3">
            Hyphenated surname parts
          </div>
          <div className="space-y-2 font-mono text-sm">
            {hyphenated_last_name_parts.map((p) => (
              <div key={p.part} className="flex justify-between border-b border-zinc-100 py-1">
                <span>{p.part}</span>
                <span className="text-zinc-700">
                  pop {formatNum(p.population)} · rank {formatNum(p.rank)} ·{" "}
                  <RiskBadge level={p.risk_level} testId={`part-risk-${p.part}`} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div
          data-testid="warnings-panel"
          className="border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900"
        >
          <div className="text-xs uppercase tracking-[0.15em] mb-2 flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5" /> Warnings
          </div>
          <ul className="list-disc pl-5 font-mono text-xs space-y-1">
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Sources */}
      <div className="text-xs text-zinc-500 font-mono">
        Sources: {data_sources.join(" · ")}
      </div>
    </div>
  );
}


function RarityPanel({ rarity, estimate }) {
  const score = rarity?.full_name_rarity_score;
  const label = rarity?.full_name_rarity_label;
  const fnScore = rarity?.first_name_rarity_score;
  const lnScore = rarity?.last_name_rarity_score;
  const fnLabel = rarity?.first_name_rarity_label;
  const lnLabel = rarity?.last_name_rarity_label;

  // Color band: 1-3 green (rare = good for matching),
  //             4-6 yellow, 7-10 red (common = bad for matching)
  const bandColor = (s) => {
    if (s == null) return "bg-zinc-300";
    if (s <= 3) return "bg-green-600";
    if (s <= 6) return "bg-yellow-500";
    return "bg-red-600";
  };
  const bandText = (s) => {
    if (s == null) return "text-zinc-500";
    if (s <= 3) return "text-green-700";
    if (s <= 6) return "text-yellow-800";
    return "text-red-700";
  };

  return (
    <div
      data-testid="rarity-panel"
      className="border border-zinc-200 p-6 md:p-8"
    >
      <div className="flex items-baseline justify-between mb-4 gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-[0.15em] text-zinc-500">
            Rarity score
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            1 = most rare · 10 = most common
          </div>
        </div>
        <div className="text-right">
          <div
            data-testid="rarity-score-value"
            className={`text-5xl font-light font-mono tracking-tighter ${bandText(
              score
            )}`}
          >
            {score ?? "—"}
            <span className="text-zinc-400 text-2xl">/10</span>
          </div>
          <div
            data-testid="rarity-label"
            className={`text-xs uppercase tracking-[0.12em] mt-1 ${bandText(
              score
            )}`}
          >
            {label || "Unknown"}
          </div>
        </div>
      </div>

      {/* 10-segment meter */}
      <div className="flex gap-1.5 mb-2" data-testid="rarity-meter">
        {Array.from({ length: 10 }, (_, i) => {
          const idx = i + 1;
          const active = score != null && idx <= score;
          return (
            <div
              key={idx}
              className={`h-3 flex-1 ${
                active ? bandColor(score) : "bg-zinc-100"
              } border border-zinc-200`}
              data-testid={`rarity-meter-cell-${idx}`}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] uppercase tracking-[0.1em] text-zinc-500 mb-6">
        <span>1 rarest</span>
        <span>10 most common</span>
      </div>

      {/* Per-component breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border-t border-zinc-200 pt-4">
        <div className="md:border-r border-zinc-200 md:pr-6 pb-4 md:pb-0">
          <div className="text-xs uppercase tracking-[0.12em] text-zinc-500 mb-1">
            First name
          </div>
          <div className="flex items-baseline gap-2">
            <span
              data-testid="first-name-rarity-score"
              className={`text-2xl font-mono font-light ${bandText(fnScore)}`}
            >
              {fnScore ?? "—"}
            </span>
            <span className="text-zinc-400 text-sm">/10</span>
            <span className="text-xs text-zinc-600 ml-2">{fnLabel || ""}</span>
          </div>
        </div>
        <div className="md:pl-6 pt-4 md:pt-0 border-t md:border-t-0 border-zinc-200">
          <div className="text-xs uppercase tracking-[0.12em] text-zinc-500 mb-1">
            Last name
          </div>
          <div className="flex items-baseline gap-2">
            <span
              data-testid="last-name-rarity-score"
              className={`text-2xl font-mono font-light ${bandText(lnScore)}`}
            >
              {lnScore ?? "—"}
            </span>
            <span className="text-zinc-400 text-sm">/10</span>
            <span className="text-xs text-zinc-600 ml-2">{lnLabel || ""}</span>
          </div>
        </div>
      </div>

      {estimate != null && (
        <div className="text-[11px] text-zinc-500 mt-4 font-mono">
          Calibration: 1 + 2·log₁₀({formatNum(estimate)}) ≈{" "}
          {(1 + 2 * Math.log10(Math.max(estimate, 1))).toFixed(2)} → clamped to{" "}
          {score}
        </div>
      )}
    </div>
  );
}
