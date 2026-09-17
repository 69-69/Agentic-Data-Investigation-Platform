import { NextRequest } from "next/server";
import { forward } from "@/lib/proxy";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  return forward(request, (await params).id);
}
