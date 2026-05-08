import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";
const API_KEY = process.env.API_KEY ?? "mesa-demo-key";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const r = await fetch(`${BACKEND_URL}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: JSON.stringify(body.payload),
  });
  const data = await r.json();
  return NextResponse.json(data, { status: r.status });
}
