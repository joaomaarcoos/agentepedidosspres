import { NextResponse } from "next/server";
import { listPrompts, savePrompt } from "@/lib/server/agente-studio";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const prompts = listPrompts();
    return NextResponse.json({ prompts });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao listar prompts" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const { slug, content } = (await request.json()) as { slug: string; content: string };
    if (!slug || typeof slug !== "string" || !slug.trim()) {
      return NextResponse.json({ error: "slug é obrigatório" }, { status: 400 });
    }
    if (typeof content !== "string") {
      return NextResponse.json({ error: "content é obrigatório" }, { status: 400 });
    }
    const prompt = savePrompt(slug.trim(), content);
    return NextResponse.json(prompt, { status: 201 });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao criar prompt" },
      { status: 500 }
    );
  }
}
