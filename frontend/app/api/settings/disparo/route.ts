import { NextResponse } from "next/server";
import { getDisparoSettings, setDisparoSetting } from "@/lib/server/settings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const settings = await getDisparoSettings();
    return NextResponse.json(settings);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao carregar configurações" },
      { status: 500 }
    );
  }
}

export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const { key, value } = body as { key: string; value: boolean };

    if (!["disparo_recorrencia_enabled", "disparo_ativacao_enabled"].includes(key)) {
      return NextResponse.json({ error: "Chave inválida" }, { status: 400 });
    }
    if (typeof value !== "boolean") {
      return NextResponse.json({ error: "Valor deve ser boolean" }, { status: 400 });
    }

    const result = await setDisparoSetting(
      key as "disparo_recorrencia_enabled" | "disparo_ativacao_enabled",
      value
    );
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Erro ao atualizar configuração" },
      { status: 500 }
    );
  }
}
