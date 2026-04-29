type StatusCardProps = {
  label: string;
  value: string | number;
  hint: string;
};

export function StatusCard({ label, value, hint }: StatusCardProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-xl shadow-black/20">
      <p className="text-sm font-medium text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-bold text-white">{value}</p>
      <p className="mt-2 text-sm text-slate-400">{hint}</p>
    </section>
  );
}
