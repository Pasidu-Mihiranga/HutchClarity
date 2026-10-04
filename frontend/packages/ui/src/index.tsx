/**
 * @clarity/ui: the design system shared by customer-web, console and verify.
 *
 * Apps import `@clarity/ui/tokens.css` once, add `@clarity/ui/tailwind-preset`
 * to their Tailwind config, and import components from here. Components carry
 * no literal colours; everything resolves through the tokens.
 */
export { cx, focusRing, useFocusTrap, useScrollLock, useControllable, mergeRefs } from "./components/utils";
export {
  Button,
  Card,
  Badge,
  Input,
  Textarea,
  Select,
  Field,
  Spinner,
  Skeleton,
} from "./components/primitives";
export type {
  ButtonProps,
  CardProps,
  BadgeProps,
  InputProps,
  TextareaProps,
  SelectProps,
  FieldProps,
  SpinnerProps,
  SkeletonProps,
} from "./components/primitives";
export { Alert, EmptyState, ErrorState } from "./components/feedback";
export type { AlertProps, EmptyStateProps, ErrorStateProps } from "./components/feedback";
export { Dialog, Tooltip, ToastProvider, useToast } from "./components/overlay";
export type { DialogProps, TooltipProps, ToastInput, ToastTone } from "./components/overlay";
export {
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableHeaderCell,
  TableCell,
  Tabs,
  TabList,
  Tab,
  TabPanel,
  Pagination,
  pageWindow,
} from "./components/data";
export type { TableProps, TableHeaderCellProps, TabsProps, PaginationProps } from "./components/data";
export { ThemeProvider, ThemeSwitcher, useTheme } from "./components/theme";
export type { ThemeChoice } from "./components/theme";
