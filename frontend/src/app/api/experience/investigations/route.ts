import { NextRequest } from "next/server";
import { forward } from "@/lib/proxy";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function POST(request: NextRequest) {
  return forward(request);
}
