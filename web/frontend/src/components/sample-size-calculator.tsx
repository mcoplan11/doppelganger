"use client";

import { useState } from "react";

// Two-tailed critical z for alpha, and z for power. Hardcoded for the offered
// options so we don't need an inverse-normal implementation.
const Z_ALPHA: Record<string, number> = { "0.10": 1.6449, "0.05": 1.95996, "0.01": 2.5758 };
const Z_POWER: Record<string, number> = { "0.80": 0.8416, "0.90": 1.2816, "0.95": 1.6449 };

const EFFECT_PRESETS = [
  { label: "Small (d = 0.2)", value: 0.2 },
  { label: "Medium (d = 0.5)", value: 0.5 },
  { label: "Large (d = 0.8)", value: 0.8 },
];

/** Per-group n for a two-sample t-test (normal approximation with Guenther's
 *  small-sample correction), or total n for a paired/one-sample design. */
function sampleSize(design: "between" | "within", d: number, za: number, zb: number): number {
  if (design === "between") {
    return Math.ceil((2 * (za + zb) ** 2) / d ** 2 + za ** 2 / 4);
  }
  return Math.ceil(((za + zb) ** 2) / d ** 2 + za ** 2 / 2);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-slate-700 mb-1">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

export function SampleSizeCalculator() {
  const [design, setDesign] = useState<"between" | "within">("between");
  const [d, setD] = useState("0.5");
  const [alpha, setAlpha] = useState("0.05");
  const [power, setPower] = useState("0.80");
  const [conditions, setConditions] = useState("2");

  const [minutes, setMinutes] = useState("10");
  const [rate, setRate] = useState("12");
  const [feePct, setFeePct] = useState("33");
  const [bufferPct, setBufferPct] = useState("10");

  const dNum = parseFloat(d);
  const k = Math.max(2, parseInt(conditions) || 2);
  const valid = Number.isFinite(dNum) && dNum > 0 && dNum <= 3;

  let perCell = 0;
  let total = 0;
  if (valid) {
    perCell = sampleSize(design, dNum, Z_ALPHA[alpha], Z_POWER[power]);
    total = design === "between" ? perCell * k : perCell;
  }

  const buffer = Math.max(0, parseFloat(bufferPct) || 0) / 100;
  const recruited = Math.ceil(total * (1 + buffer));
  const perHead = ((parseFloat(minutes) || 0) / 60) * (parseFloat(rate) || 0);
  const fee = Math.max(0, parseFloat(feePct) || 0) / 100;
  const cost = recruited * perHead * (1 + fee);

  const money = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 sm:p-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Study design">
          <select value={design} onChange={(e) => setDesign(e.target.value as "between" | "within")} className={inputCls}>
            <option value="between">Between-subjects (independent groups)</option>
            <option value="within">Within-subjects (paired)</option>
          </select>
        </Field>
        <Field label="Expected effect size (Cohen's d)">
          <input
            type="number"
            step="0.05"
            min="0.05"
            max="3"
            value={d}
            onChange={(e) => setD(e.target.value)}
            className={inputCls}
          />
          <span className="flex gap-2 mt-1.5">
            {EFFECT_PRESETS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setD(String(p.value))}
                className={`text-xs rounded-full border px-2 py-0.5 ${
                  dNum === p.value
                    ? "border-blue-600 text-blue-700 bg-blue-50"
                    : "border-slate-300 text-slate-500 hover:border-slate-400"
                }`}
              >
                {p.label}
              </button>
            ))}
          </span>
        </Field>
        <Field label="Significance level (two-tailed α)">
          <select value={alpha} onChange={(e) => setAlpha(e.target.value)} className={inputCls}>
            <option value="0.05">α = .05 (convention)</option>
            <option value="0.01">α = .01 (strict)</option>
            <option value="0.10">α = .10 (lenient)</option>
          </select>
        </Field>
        <Field label="Statistical power">
          <select value={power} onChange={(e) => setPower(e.target.value)} className={inputCls}>
            <option value="0.80">80% (convention)</option>
            <option value="0.90">90%</option>
            <option value="0.95">95%</option>
          </select>
        </Field>
        {design === "between" && (
          <Field label="Number of conditions">
            <input
              type="number"
              min="2"
              max="30"
              value={conditions}
              onChange={(e) => setConditions(e.target.value)}
              className={inputCls}
            />
          </Field>
        )}
      </div>

      <div className="mt-6 rounded-lg bg-slate-50 border border-slate-200 p-5">
        {valid ? (
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <p className="text-sm text-slate-500">
                {design === "between" ? "Participants per condition" : "Participants (within-subjects)"}
              </p>
              <p className="text-3xl font-bold text-slate-900">{perCell.toLocaleString()}</p>
            </div>
            {design === "between" && (
              <div>
                <p className="text-sm text-slate-500">Total across {k} conditions</p>
                <p className="text-3xl font-bold text-slate-900">{total.toLocaleString()}</p>
              </div>
            )}
            <p className="text-xs text-slate-500 max-w-[16rem]">
              Based on a two-tailed t-test at α = {alpha}, {Math.round(parseFloat(power) * 100)}%
              power, d = {dNum}. Cross-check complex designs in G*Power.
            </p>
          </div>
        ) : (
          <p className="text-sm text-slate-600">Enter an effect size between 0.05 and 3 to see the required sample.</p>
        )}
      </div>

      <h3 className="font-serif text-xl font-bold text-slate-900 mt-8 mb-3">What will it cost to field?</h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Field label="Study length (min)">
          <input type="number" min="1" value={minutes} onChange={(e) => setMinutes(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Pay rate ($/hr)">
          <input type="number" min="0" step="0.5" value={rate} onChange={(e) => setRate(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Platform fee (%)">
          <input type="number" min="0" max="100" value={feePct} onChange={(e) => setFeePct(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Exclusion buffer (%)">
          <input type="number" min="0" max="100" value={bufferPct} onChange={(e) => setBufferPct(e.target.value)} className={inputCls} />
        </Field>
      </div>

      {valid && (
        <div className="mt-4 rounded-lg bg-slate-50 border border-slate-200 p-5 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <p className="text-sm text-slate-500">Recruit (with {Math.round(buffer * 100)}% buffer)</p>
            <p className="text-2xl font-bold text-slate-900">{recruited.toLocaleString()} people</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Payment per participant</p>
            <p className="text-2xl font-bold text-slate-900">{money(perHead)}</p>
          </div>
          <div>
            <p className="text-sm text-slate-500">Estimated total cost</p>
            <p className="text-3xl font-bold text-blue-700">{money(cost)}</p>
          </div>
        </div>
      )}
    </div>
  );
}
