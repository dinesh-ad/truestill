import { useState } from "react";
import { motion } from "framer-motion";
import {
  FolderOpen,
  Map,
  Download,
  HardDrive,
  Search,
  BarChart2,
  Settings,
  AlertTriangle,
  Copy,
  Move,
  ArrowRightLeft,
  Database,
} from "lucide-react";

export default function TruestillApp() {
  const [activeTab, setActiveTab] = useState("organize");
  const [organizeMethod, setOrganizeMethod] = useState("copy");

  const navGroups = [
    {
      title: "MAIN",
      items: [
        { id: "organize", label: "Organize", icon: FolderOpen },
        { id: "trips", label: "Trips & events", icon: Map },
        { id: "import", label: "Import", icon: Download },
        { id: "backups", label: "Backups", icon: HardDrive },
        { id: "find", label: "Find", icon: Search },
        { id: "stats", label: "Stats", icon: BarChart2 },
      ],
    },
    {
      title: "SETTINGS",
      items: [{ id: "settings", label: "Settings", icon: Settings }],
    },
  ];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-zinc-950 font-sans">
      {/* ================= SIDEBAR ================= */}
      <div className="z-20 flex h-full w-64 shrink-0 flex-col border-r border-white/5 bg-[#09090B] text-slate-300 shadow-2xl">
        {/* Brand Header */}
        <div className="flex items-center gap-4 px-6 py-8">
          {/* The Clean, Unified Monochrome 'T' Logo */}
          <div className="flex h-10 w-10 shrink-0 items-center justify-center text-rose-500 drop-shadow-[0_0_15px_rgba(244,63,94,0.4)]">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 100 100"
              className="h-full w-full"
              aria-hidden
            >
              <path
                fill="none"
                stroke="currentColor"
                strokeWidth="32"
                strokeLinecap="round"
                strokeLinejoin="round"
                d="
                  M 25 25 L 75 25
                  M 50 25 L 50 80
                "
              />
              <circle cx="34" cy="41" r="16" fill="currentColor" />
              <circle cx="66" cy="41" r="16" fill="currentColor" />
            </svg>
          </div>
          <span className="text-xl font-bold tracking-wide text-white">
            Truestill<span className="text-rose-500">.</span>
          </span>
        </div>

        {/* Navigation */}
        <nav className="custom-scrollbar flex-1 space-y-8 overflow-y-auto px-3 pb-4">
          {navGroups.map((group) => (
            <div key={group.title}>
              <h3 className="mb-3 px-3 text-xs font-bold tracking-widest text-zinc-500 uppercase">
                {group.title}
              </h3>
              <ul className="space-y-1">
                {group.items.map((item) => {
                  const isActive = activeTab === item.id;
                  const Icon = item.icon;

                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => setActiveTab(item.id)}
                        className="group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                      >
                        {isActive && (
                          <motion.div
                            layoutId="sidebar-active"
                            className="absolute inset-0 rounded-xl border border-rose-500/20 bg-rose-500/10"
                            initial={false}
                            transition={{
                              type: "spring",
                              bounce: 0.2,
                              duration: 0.6,
                            }}
                          />
                        )}

                        {!isActive && (
                          <div className="absolute inset-0 rounded-xl bg-white/0 transition-colors duration-200 group-hover:bg-white/5" />
                        )}

                        <Icon
                          className={`relative z-10 h-4 w-4 transition-colors duration-300 ${
                            isActive
                              ? "text-rose-400"
                              : "text-zinc-500 group-hover:text-zinc-300"
                          }`}
                        />
                        <span
                          className={`relative z-10 transition-colors duration-300 ${
                            isActive
                              ? "font-semibold text-rose-50"
                              : "text-zinc-400 group-hover:text-zinc-200"
                          }`}
                        >
                          {item.label}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Bottom Status Widget */}
        <div className="p-4">
          <motion.div
            whileHover={{ scale: 1.02 }}
            className="group relative cursor-pointer overflow-hidden rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 shadow-lg"
          >
            <div className="pointer-events-none absolute -top-4 -right-4 h-16 w-16 rounded-full bg-rose-500/20 blur-xl transition-all group-hover:bg-rose-500/30" />
            <div className="relative z-10 flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
              <div className="space-y-1 text-xs">
                <p className="font-semibold text-rose-400">
                  395 files in only one place:
                </p>
                <p className="font-medium text-zinc-300">Morrowkeep</p>
                <p className="truncate text-zinc-500 opacity-80">
                  /home/dino...catalog.sqlite
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* ================= MAIN CONTENT ================= */}
      {activeTab === "organize" ? (
        <OrganizeMain
          organizeMethod={organizeMethod}
          setOrganizeMethod={setOrganizeMethod}
        />
      ) : (
        <PlaceholderMain name={labelFor(activeTab)} />
      )}
    </div>
  );
}

function labelFor(id: string): string {
  const map: Record<string, string> = {
    organize: "Organize",
    trips: "Trips & events",
    import: "Import",
    backups: "Backups",
    find: "Find",
    stats: "Stats",
    settings: "Settings",
  };
  return map[id] ?? id;
}

function PlaceholderMain({ name }: { name: string }) {
  return (
    <div className="relative h-full flex-1 overflow-y-auto bg-gradient-to-br from-rose-50 via-white to-orange-50 text-slate-900">
      <div className="pointer-events-none absolute top-[-10%] left-[-10%] h-[40rem] w-[40rem] rounded-full bg-rose-200/40 blur-3xl" />
      <div className="pointer-events-none absolute right-[-10%] bottom-[-10%] h-[40rem] w-[40rem] rounded-full bg-orange-200/30 blur-3xl" />
      <div className="relative z-10 flex min-h-full items-center justify-center p-8">
        <div className="rounded-2xl border border-white/60 bg-white/70 px-10 py-8 text-center shadow-xl backdrop-blur-2xl">
          <p className="text-xs font-bold tracking-widest text-slate-500 uppercase">
            Scratch preview
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            {name}
          </h1>
          <p className="mt-2 max-w-sm text-sm text-slate-500">
            Only Organize is mocked here. Use the rail to try the sliding active
            pill.
          </p>
        </div>
      </div>
    </div>
  );
}

function OrganizeMain({
  organizeMethod,
  setOrganizeMethod,
}: {
  organizeMethod: string;
  setOrganizeMethod: (id: string) => void;
}) {
  return (
    <div className="relative h-full flex-1 overflow-y-auto bg-gradient-to-br from-rose-50 via-white to-orange-50 text-slate-900">
      {/* Liquid Glass Background Elements */}
      <div className="pointer-events-none absolute top-[-10%] left-[-10%] h-[40rem] w-[40rem] rounded-full bg-rose-200/40 blur-3xl" />
      <div className="pointer-events-none absolute right-[-10%] bottom-[-10%] h-[40rem] w-[40rem] rounded-full bg-orange-200/30 blur-3xl" />

      <div className="relative z-10 flex min-h-full gap-8 p-8">
        <div className="max-w-3xl flex-1 space-y-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          >
            <h1 className="mb-2 text-4xl font-semibold tracking-tight text-slate-900">
              Organize
            </h1>
            <p className="max-w-prose text-lg text-slate-600">
              Choose how to organize: copy into a destination, move into a
              destination, or reorganize this folder in place.
            </p>
          </motion.div>

          {/* Primary Form Panel */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: "easeOut" }}
            className="space-y-8 rounded-2xl border border-white/60 bg-white/70 p-8 shadow-xl backdrop-blur-2xl"
          >
            {/* Folder to organize */}
            <div className="space-y-4">
              <h2 className="text-xs font-bold tracking-widest text-slate-500 uppercase">
                Folder to organize
              </h2>

              <div className="flex flex-wrap gap-2">
                {["Home", "Pictures", "Downloads", "Desktop", "Documents"].map(
                  (folder) => (
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      key={folder}
                      type="button"
                      className="rounded-full border border-white/80 bg-white/50 px-4 py-1.5 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-white hover:text-slate-900"
                    >
                      {folder}
                    </motion.button>
                  ),
                )}
              </div>

              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="e.g. /home/you/Pictures"
                  className="flex-1 rounded-xl border border-white/80 bg-white/50 px-4 py-2.5 text-sm shadow-inner transition-all placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-rose-500/50 focus:outline-none"
                />
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-all hover:text-slate-900"
                >
                  <FolderOpen className="h-4 w-4" />
                  Browse
                </motion.button>
              </div>
            </div>

            <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent" />

            {/* Action Selection */}
            <div className="space-y-4">
              <h2 className="text-xs font-bold tracking-widest text-slate-500 uppercase">
                How to organize
              </h2>

              <div className="grid gap-3" role="radiogroup">
                {[
                  {
                    id: "copy",
                    title: "Copy into an organized folder",
                    desc: "Originals stay where they are.",
                    icon: Copy,
                  },
                  {
                    id: "move",
                    title: "Move into an organized folder",
                    desc: "Same-drive: rename. Cross-drive: copy, verify, then delete source.",
                    icon: Move,
                  },
                  {
                    id: "reorganize",
                    title: "Reorganize in this same folder",
                    desc: "Moves by rename only; never falls back to copy.",
                    icon: ArrowRightLeft,
                  },
                ].map((method) => {
                  const isActive = organizeMethod === method.id;
                  const Icon = method.icon;

                  return (
                    <label
                      key={method.id}
                      className="group relative flex cursor-pointer rounded-xl p-4"
                    >
                      <input
                        type="radio"
                        name="method"
                        value={method.id}
                        checked={isActive}
                        onChange={(e) => setOrganizeMethod(e.target.value)}
                        className="sr-only"
                      />

                      {isActive && (
                        <motion.div
                          layoutId="active-card-bg"
                          className="absolute inset-0 rounded-xl border-2 border-rose-500 bg-rose-500/10 shadow-sm"
                          initial={false}
                          transition={{
                            type: "spring",
                            bounce: 0.2,
                            duration: 0.6,
                          }}
                        />
                      )}

                      {!isActive && (
                        <div className="absolute inset-0 rounded-xl border border-white/80 bg-white/40 shadow-sm transition-colors group-hover:bg-white/60" />
                      )}

                      <div className="relative z-10 flex w-full items-start gap-4">
                        <div
                          className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors duration-300 ${isActive ? "bg-rose-500 text-white shadow-md shadow-rose-500/20" : "bg-slate-100 text-slate-400 group-hover:text-slate-600"}`}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <span
                            className={`block text-sm font-semibold transition-colors duration-300 ${isActive ? "text-rose-950" : "text-slate-700"}`}
                          >
                            {method.title}
                          </span>
                          <span className="mt-1 block text-sm text-slate-500">
                            {method.desc}
                          </span>
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent" />

            {/* Destination Folder */}
            <div className="space-y-4">
              <h2 className="text-xs font-bold tracking-widest text-slate-500 uppercase">
                Organized folder (where sorted copies go)
              </h2>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="e.g. /home/you/Pictures/Truestill"
                  className="flex-1 rounded-xl border border-white/80 bg-white/50 px-4 py-2.5 text-sm shadow-inner transition-all placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-rose-500/50 focus:outline-none"
                />
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition-all hover:text-slate-900"
                >
                  <FolderOpen className="h-4 w-4" />
                  Browse
                </motion.button>
              </div>
            </div>
          </motion.div>

          {/* Additional Options */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2, ease: "easeOut" }}
            className="space-y-8 pl-2"
          >
            <div className="space-y-4">
              <label className="group flex cursor-pointer items-center gap-3">
                <div className="relative flex h-5 w-5 items-center justify-center rounded border border-slate-300 bg-white/60 shadow-sm transition-all group-hover:border-rose-400">
                  <input type="checkbox" className="peer sr-only" />
                  <div className="h-3 w-3 rounded-sm bg-rose-500 opacity-0 transition-opacity peer-checked:opacity-100" />
                </div>
                <span className="text-sm text-slate-600 transition-colors group-hover:text-slate-900">
                  Skip files with no date (they won&apos;t be sorted into an
                  Undated folder)
                </span>
              </label>
              <label className="group flex cursor-pointer items-center gap-3">
                <div className="relative flex h-5 w-5 items-center justify-center rounded border border-slate-300 bg-white/60 shadow-sm transition-all group-hover:border-rose-400">
                  <input type="checkbox" className="peer sr-only" />
                  <div className="h-3 w-3 rounded-sm bg-rose-500 opacity-0 transition-opacity peer-checked:opacity-100" />
                </div>
                <span className="text-sm text-slate-600 transition-colors group-hover:text-slate-900">
                  Re-read metadata (bypass cache if another tool edited tags)
                </span>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="button"
                className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white/80 px-6 py-3 text-sm font-semibold text-slate-900 shadow-sm backdrop-blur transition-all hover:bg-white hover:shadow-md"
              >
                <Search className="h-4 w-4 text-rose-500" />
                Look inside
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: "#18181b" }}
                whileTap={{ scale: 0.98 }}
                type="button"
                className="flex items-center gap-2 rounded-xl bg-zinc-900 px-6 py-3 text-sm font-semibold text-white shadow-md transition-all hover:shadow-lg"
              >
                <Database className="h-4 w-4 text-orange-400" />
                Check for duplicates
              </motion.button>
              <span className="text-sm text-slate-500">
                Look inside first to see what is in the folder.
              </span>
            </div>
          </motion.div>
        </div>

        {/* Right Sidebar Stats */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{
            duration: 0.6,
            delay: 0.3,
            type: "spring",
            bounce: 0.1,
          }}
          className="w-80 shrink-0"
        >
          <div className="sticky top-8 space-y-6 rounded-2xl border border-white/60 bg-white/60 p-6 shadow-xl backdrop-blur-2xl">
            <div>
              <h3 className="mb-4 text-xs font-bold tracking-widest text-slate-500 uppercase">
                Your Library
              </h3>
              <div className="text-2xl font-semibold tracking-tight text-slate-900">
                2,676{" "}
                <span className="text-lg font-normal text-slate-500">
                  photos
                </span>
              </div>
              <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
                19{" "}
                <span className="text-lg font-normal text-slate-500">
                  videos
                </span>
              </div>
              <div className="mt-3 inline-block rounded-full border border-rose-200/50 bg-rose-100/50 px-3 py-1 text-xs font-semibold text-rose-800">
                10.4 GB Total
              </div>
            </div>

            <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent" />

            <div className="space-y-4">
              <div className="group">
                <div className="mb-1 text-xs font-semibold tracking-wider text-slate-500 uppercase">
                  In at least
                </div>
                <div className="text-sm font-medium text-slate-900 transition-colors group-hover:text-rose-600">
                  1 place
                </div>
              </div>

              <div className="group">
                <div className="mb-1 text-xs font-semibold tracking-wider text-slate-500 uppercase">
                  Never checked
                </div>
                <div className="text-sm font-medium text-slate-900 transition-colors group-hover:text-rose-600">
                  Morrowkeep
                </div>
              </div>

              <div className="group">
                <div className="mb-1 text-xs font-semibold tracking-wider text-slate-500 uppercase">
                  Not on any drive
                </div>
                <div className="inline-block rounded-lg border border-amber-200/50 bg-amber-50/50 p-2 text-sm font-medium text-amber-600 transition-all group-hover:bg-amber-100/50">
                  31 items
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
