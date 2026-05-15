import { NextResponse } from "next/server";
import { getPrompt, savePrompt, deletePrompt } from "@/lib/server/agente-studio";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: { slug: string } }) {
  try {
    const prompt = getPrompt(params.slug);
    if (!prompt) {
      return NextResponse.json({ error: "Prompt não encontrado" }, { status: 404 });
    }
    return NextResponse.json(prompt);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao buscar prompt" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request, { params }: { params: { slug: string } }) {
  try {
    const { content } = (await request.json()) as { content: string };
    if (typeof content !== "string") {
      return NextResponse.json({ error: "content é obrigatório" }, { status: 400 });
    }
    const prompt = savePrompt(params.slug, content);
    return NextResponse.json(prompt);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao salvar prompt" },
      { status: 500 }
    );
  }
}

export async function DELETE(_req: Request, { params }: { params: { slug: string } }) {
  try {
    deletePrompt(params.slug);
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao deletar prompt" },
      { status: 500 }
    );
  }
}
