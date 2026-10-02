"use client";

import type { StudentModel } from "@/lib/api";
import { LearningProgress } from "./LearningProgress";

export function MasteryTree({ mastery }: { mastery: StudentModel["mastery"] }) {
  if (!mastery.length) return null;
  const grouped = mastery.reduce<Record<string, StudentModel["mastery"]>>((acc, item) => {
    acc[item.subject] = acc[item.subject] ?? [];
    acc[item.subject].push(item);
    return acc;
  }, {});
  return (
    <div className="space-y-5">
      {Object.entries(grouped).map(([subject, topics]) => (
        <div key={subject}>
          <p className="text-xs text-ink-400">{subject}</p>
          <div className="mt-3 space-y-3">
            {topics.map((item) => (
              <LearningProgress
                key={`${item.subject}-${item.topic}`}
                label={item.topic}
                value={item.mastery}
                detail={`${item.attempts}`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
