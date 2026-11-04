import { useFilters } from "@/hooks/useFilters";

const pollutants = ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"];

export function FilterBar() {
  const { filters, update } = useFilters();
  return (
    <form className="mx-auto grid max-w-7xl grid-cols-2 gap-3 px-4 py-3 md:grid-cols-5" onSubmit={(e) => e.preventDefault()}>
      <label className="text-xs text-stone-600">
        City
        <input
          className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm"
          value={filters.city}
          onChange={(e) => update({ city: e.target.value })}
        />
      </label>
      <label className="text-xs text-stone-600">
        Pollutant
        <select
          className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm"
          value={filters.pollutant}
          onChange={(e) => update({ pollutant: e.target.value })}
        >
          {pollutants.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </label>
      <label className="text-xs text-stone-600">
        From
        <input
          type="date"
          className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm"
          value={filters.from}
          onChange={(e) => update({ from: e.target.value })}
        />
      </label>
      <label className="text-xs text-stone-600">
        To
        <input
          type="date"
          className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm"
          value={filters.to}
          onChange={(e) => update({ to: e.target.value })}
        />
      </label>
      <label className="text-xs text-stone-600">
        Grid resolution (m)
        <select
          className="mt-1 w-full rounded-md border border-stone-300 bg-white px-2 py-1.5 text-sm"
          value={filters.resolution}
          onChange={(e) => update({ resolution: e.target.value })}
        >
          <option value="500">500</option>
          <option value="1000">1000</option>
        </select>
      </label>
    </form>
  );
}
