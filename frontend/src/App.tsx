import { Wordmark, SpecLabel } from "./ui";

// D1 placeholder: the console routes arrive in D2, the landing in D3.
export default function App() {
  return (
    <main className="grid min-h-full place-items-center gap-6 p-12">
      <Wordmark />
      <SpecLabel k="Console" rest={["Coming in D2"]} />
    </main>
  );
}
