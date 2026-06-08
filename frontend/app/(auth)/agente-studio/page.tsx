"use client";

import { useEffect, useState, useCallback } from "react";
import { agenteStudioApi } from "@/lib/api";
import type { PromptFile } from "@/lib/types";
import { Plus, Trash2, Save, FileText, Shield } from "lucide-react";

function slugify(text: string) {
  return text
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_-]/g, "")
    .slice(0, 50);
}

export default function AgenteStudioPage() {
  const [prompts, setPrompts] = useState<PromptFile[]>([]);
  const [selected, setSelected] = useState<PromptFile | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newSlugInput, setNewSlugInput] = useState("");
  const [showNewForm, setShowNewForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [bufferSeconds, setBufferSeconds] = useState(5);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await agenteStudioApi.list();
      const settings = await agenteStudioApi.getSettings().catch(() => null);
      if (settings) setBufferSeconds(settings.message_buffer_seconds);
      setPrompts(data.prompts);
      if (data.prompts.length > 0 && !selected) {
        const first = data.prompts[0];
        setSelected(first);
        setEditorContent(first.content);
        setDirty(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar prompts");
    } finally {
      setLoading(false);
    }
  }, [selected]);

  useEffect(() => {
    load();
  }, []);

  function selectPrompt(p: PromptFile) {
    if (dirty && !confirm("Há alterações não salvas. Descartar?")) return;
    setSelected(p);
    setEditorContent(p.content);
    setDirty(false);
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await agenteStudioApi.update(selected.slug, editorContent);
      setSelected(updated);
      setDirty(false);
      setPrompts((prev) => prev.map((p) => (p.slug === updated.slug ? updated : p)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(p: PromptFile) {
    if (p.core) return;
    if (!confirm(`Remover "${p.label || p.slug}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await agenteStudioApi.delete(p.slug);
      const updated = prompts.filter((x) => x.slug !== p.slug);
      setPrompts(updated);
      if (selected?.slug === p.slug) {
        const next = updated[0] ?? null;
        setSelected(next);
        setEditorContent(next?.content ?? "");
        setDirty(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover");
    }
  }

  async function handleCreate() {
    const slug = slugify(newSlugInput);
    if (!slug) return;
    setCreating(true);
    setError(null);
    try {
      const created = await agenteStudioApi.create(slug, `# ${newSlugInput}\n\n`);
      setPrompts((prev) => [...prev, created]);
      setSelected(created);
      setEditorContent(created.content);
      setDirty(false);
      setShowNewForm(false);
      setNewSlugInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar");
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveSettings() {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      const saved = await agenteStudioApi.updateSettings({
        message_buffer_seconds: bufferSeconds,
      });
      setBufferSeconds(saved.message_buffer_seconds);
      setSettingsMessage("Configurações salvas");
    } catch (e) {
      setSettingsMessage(e instanceof Error ? e.message : "Erro ao salvar configurações");
    } finally {
      setSettingsSaving(false);
    }
  }

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden max-[760px]:flex-col">
      {/* Left panel */}
      <aside className="w-64 shrink-0 border-r border-gray-200 bg-white flex flex-col max-[760px]:w-full max-[760px]:max-h-64 max-[760px]:border-r-0 max-[760px]:border-b">
        <div className="p-3 border-b border-gray-200 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Prompts</span>
          <button
            onClick={() => setShowNewForm((v) => !v)}
            className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
            title="Novo prompt"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {showNewForm && (
          <div className="p-3 border-b border-gray-200 bg-gray-50">
            <input
              type="text"
              placeholder="Nome (ex: tom_formal)"
              value={newSlugInput}
              onChange={(e) => setNewSlugInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="w-full text-sm border border-gray-300 rounded px-2 py-1 mb-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating || !newSlugInput.trim()}
                className="flex-1 text-xs bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? "Criando..." : "Criar"}
              </button>
              <button
                onClick={() => { setShowNewForm(false); setNewSlugInput(""); }}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        <nav className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-sm text-gray-400">Carregando...</div>
          ) : (
            prompts.map((p) => (
              <button
                key={p.slug}
                onClick={() => selectPrompt(p)}
                className={`w-full text-left px-3 py-2.5 border-b border-gray-100 hover:bg-gray-50 flex items-start gap-2 group ${
                  selected?.slug === p.slug ? "bg-blue-50 border-l-2 border-l-blue-500" : ""
                }`}
              >
                <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-medium text-gray-700 truncate">
                      {p.label || p.slug}
                    </span>
                    {p.core && (
                      <span title="Essencial">
                        <Shield className="w-3 h-3 text-amber-500 shrink-0" />
                      </span>
                    )}
                  </div>
                  {p.description && (
                    <p className="text-xs text-gray-400 truncate">{p.description}</p>
                  )}
                  <p className="text-xs text-gray-300">{p.lines} linhas</p>
                </div>
                {!p.core && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(p); }}
                    className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 hover:text-red-600 text-gray-400 shrink-0"
                    title="Remover"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </button>
            ))
          )}
        </nav>

        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className="text-xs font-semibold text-gray-600 mb-2">Runtime</div>
          <label className="block text-xs text-gray-500 mb-1">
            Buffer de mensagens (segundos)
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              max={30}
              step={0.5}
              value={bufferSeconds}
              onChange={(e) => setBufferSeconds(Number(e.target.value))}
              className="w-20 text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={handleSaveSettings}
              disabled={settingsSaving}
              className="text-xs bg-gray-800 text-white rounded px-2 py-1 hover:bg-gray-900 disabled:opacity-50"
            >
              {settingsSaving ? "..." : "Salvar"}
            </button>
          </div>
          {settingsMessage && (
            <p className="text-xs text-gray-400 mt-2 truncate">{settingsMessage}</p>
          )}
        </div>
      </aside>

      {/* Editor panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {selected ? (
          <>
            <div className="px-4 py-2.5 border-b border-gray-200 bg-white flex items-center justify-between shrink-0">
              <div>
                <h2 className="text-sm font-semibold text-gray-800">
                  {selected.label || selected.slug}
                  {dirty && <span className="ml-1 text-blue-500">•</span>}
                </h2>
                {selected.description && (
                  <p className="text-xs text-gray-400">{selected.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {error && (
                  <span className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded">{error}</span>
                )}
                <button
                  onClick={handleSave}
                  disabled={saving || !dirty}
                  className="flex items-center gap-1.5 text-sm bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>

            <textarea
              value={editorContent}
              onChange={(e) => { setEditorContent(e.target.value); setDirty(true); }}
              className="flex-1 w-full resize-none font-mono text-sm p-4 focus:outline-none bg-gray-50 text-gray-800 leading-relaxed"
              spellCheck={false}
            />

            <div className="px-4 py-1.5 border-t border-gray-200 bg-white flex items-center justify-between shrink-0">
              <span className="text-xs text-gray-400">{selected.filename}</span>
              <span className="text-xs text-gray-400">
                {editorContent.split("\n").length} linhas ·{" "}
                {editorContent.length} chars
              </span>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-sm">Selecione um prompt para editar</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
