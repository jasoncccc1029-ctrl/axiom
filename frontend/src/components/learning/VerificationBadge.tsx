import { cn } from "@/lib/utils";

const STUDENT_LABELS: Record<string, string> = {
  VERIFIED: "已驗證",
  FAILED: "未通過",
  PARTIALLY_VERIFIED: "部分確認",
  NEEDS_REVIEW: "待你確認",
  NOT_VERIFIABLE: "尚無法驗證",
};

export function verificationStudentLabel(status: string): string {
  return STUDENT_LABELS[status] ?? status.replaceAll("_", " ");
}

export function VerificationBadge({ status }: { status: string }) {
  const verified = status === "VERIFIED";
  const failed = status === "FAILED";
  const partial = status === "PARTIALLY_VERIFIED";
  const needsReview = status === "NEEDS_REVIEW" || status === "NOT_VERIFIABLE";
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
        verified && "bg-emerald-50 text-emerald-700",
        failed && "bg-red-50 text-red-700",
        (partial || needsReview || (!verified && !failed)) && "bg-amber-50 text-amber-700"
      )}
      title={status}
    >
      {verificationStudentLabel(status)}
    </span>
  );
}
