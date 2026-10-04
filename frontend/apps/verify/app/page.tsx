export default function VerifyHomePage() {
  return (
    <main className="space-y-4 text-center">
      <h1 className="text-2xl font-semibold">Receipt verification</h1>
      <p className="text-sm text-slate-600">
        Open the link printed on a Trust Receipt, or scan its QR code. A
        receipt link looks like{" "}
        <code className="rounded bg-slate-100 px-1">/r/TR-2027-000001</code>.
      </p>
      <p className="text-xs text-slate-500">
        Checking a receipt needs no sign-in: the page asks the service to
        recompute the hash chain and the signature, and shows what it answers.
      </p>
    </main>
  );
}
