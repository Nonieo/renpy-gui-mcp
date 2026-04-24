export function Stub({ title, description }: { title: string; description: string }) {
  return (
    <div className="h-full grid place-items-center p-12">
      <div className="max-w-md text-center space-y-3">
        <h2 className="text-xl font-semibold text-zinc-700">{title}</h2>
        <p className="text-sm text-zinc-500 leading-relaxed">{description}</p>
        <p className="text-xs text-zinc-400 italic">
          Backend reads are wired through the renpy-mcp server; this panel just hasn't been
          built out yet.
        </p>
      </div>
    </div>
  );
}
