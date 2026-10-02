import Link from "next/link";

export default function VerifyHomePage() {
  return (
    <main className="space-y-4 text-center">
      <h1 className="text-2xl font-semibold">Receipt verification</h1>
      <p className="text-sm text-slate-600">
        Open a receipt link like{" "}
        <code className="rounded bg-slate-100 px-1">/r/TR-2027-000001</code>
      </p>
      <Link
        href="/r/TR-demo"
        className="inline-block text-sm text-sky-700 hover:underline"
      >
        Try demo receipt →
      </Link>
    </main>
  );
}
