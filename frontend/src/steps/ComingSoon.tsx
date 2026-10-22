import { Construction } from "lucide-react"

import { PageHeader } from "@/components/PageHeader"
import { Card, CardContent } from "@/components/ui/card"

export function ComingSoon({ title, description }: { title: string; description: string }) {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={title} title={title} description={description} />
      <Card>
        <CardContent className="flex items-center gap-3 text-muted-foreground">
          <Construction className="size-5" />
          Esta etapa ainda está em construção.
        </CardContent>
      </Card>
    </div>
  )
}
