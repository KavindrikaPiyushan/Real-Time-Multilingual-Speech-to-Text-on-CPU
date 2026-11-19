const LANGUAGES = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'English', label: 'English' },
  { value: 'Chinese', label: 'Mandarin Chinese' },
  { value: 'Indonesian', label: 'Bahasa Indonesia' },
]

const CHUNK_SIZES = [
  { value: 500, label: '0.5 s' },
  { value: 1000, label: '1 s' },
  { value: 2000, label: '2 s (default)' },
  { value: 5000, label: '5 s' },
]

function Select({ label, value, onChange, options, disabled }) {
  return (
    <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
      {label}
      <select
        className="rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm font-normal normal-case tracking-normal text-slate-900 shadow-sm outline-none transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark]"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100">
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function LanguageSelector({ language, onLanguage, chunkMs, onChunkMs, disabled }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Select label="Language" value={language} onChange={onLanguage} options={LANGUAGES} disabled={disabled} />
      <Select
        label="Audio chunk size" value={chunkMs} onChange={(v) => onChunkMs(Number(v))}
        options={CHUNK_SIZES} disabled={disabled}
      />
    </div>
  )
}
