export default function FullScreenLoader() {
  return (
    <div className="flex h-screen items-center justify-center">
      <svg
        viewBox="0 0 64 64"
        className="size-14"
        role="img"
        aria-label="Loading"
      >
        <rect width="64" height="64" rx="15" fill="#059669" />
        <path
          className="stride-loader__short"
          d="M13.5 31 20 37.5"
          stroke="#A7F3D0"
          strokeWidth="9"
          strokeLinecap="round"
        />
        <path
          className="stride-loader__long"
          d="M29.5 45.5 49.5 19"
          stroke="#FFFFFF"
          strokeWidth="9"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}
