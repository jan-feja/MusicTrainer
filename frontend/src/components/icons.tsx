/** Small inline SVG icons (Material Design paths, Apache-2.0). Size follows the font size. */
import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function Icon({ path, ...props }: IconProps & { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="currentColor"
      aria-hidden="true"
      {...props}
    >
      <path d={path} />
    </svg>
  )
}

export const PlayIcon = (props: IconProps) => <Icon path="M8 5v14l11-7z" {...props} />

export const PauseIcon = (props: IconProps) => (
  <Icon path="M6 19h4V5H6v14zm8-14v14h4V5h-4z" {...props} />
)

export const VolumeIcon = (props: IconProps) => (
  <Icon
    path="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"
    {...props}
  />
)

export const MutedIcon = (props: IconProps) => (
  <Icon
    path="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3 3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4 9.91 6.09 12 8.18V4z"
    {...props}
  />
)

export const FullscreenIcon = (props: IconProps) => (
  <Icon
    path="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"
    {...props}
  />
)

export const ExitFullscreenIcon = (props: IconProps) => (
  <Icon
    path="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"
    {...props}
  />
)

export const LoopIcon = (props: IconProps) => (
  <Icon path="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" {...props} />
)

export const CheckIcon = (props: IconProps) => (
  <Icon path="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" {...props} />
)

export const SearchIcon = (props: IconProps) => (
  <Icon
    path="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
    {...props}
  />
)

export const DeleteIcon = (props: IconProps) => (
  <Icon
    path="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
    {...props}
  />
)

export const DownloadIcon = (props: IconProps) => (
  <Icon path="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" {...props} />
)

export const AddIcon = (props: IconProps) => (
  <Icon path="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" {...props} />
)

export const EditIcon = (props: IconProps) => (
  <Icon
    path="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"
    {...props}
  />
)

export const SpeedIcon = (props: IconProps) => (
  <Icon
    path="m20.38 8.57-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zm-9.79 6.84a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z"
    {...props}
  />
)

/** Mixer sliders. */
export const MixIcon = (props: IconProps) => (
  <Icon
    path="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z"
    {...props}
  />
)

export const MetronomeIcon = (props: IconProps) => (
  <svg
    viewBox="0 0 24 24"
    width="1em"
    height="1em"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...props}
  >
    <path d="M9 3h6l4 18H5z" />
    <path d="m12 16 5-9" />
  </svg>
)
