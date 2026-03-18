// Minimal layout for the login page — no sidebar, no auth wrapper
export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
