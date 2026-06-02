import {
  ArrowUpRightIcon,
  BoxesIcon,
  CheckCircle2Icon,
  ClipboardListIcon,
  PackageCheckIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const projects = [
  {
    name: "Clinical Case Workspace",
    score: 92,
    status: "Demo ready",
    bundle: "Decision support",
    gap: "Create role-based demo script",
  },
  {
    name: "Evidence Search",
    score: 86,
    status: "Package next",
    bundle: "Evidence automation",
    gap: "Add repeatable result export",
  },
  {
    name: "Probability Tools",
    score: 81,
    status: "Bundle fit",
    bundle: "Clinical reasoning",
    gap: "Clarify buyer-facing outcomes",
  },
];

const bundleRows = [
  ["Decision support", "Strong", "Case workspace + evidence + probability"],
  ["Sales demo kit", "Medium", "Narrative route + sample cases + talk track"],
  ["Workflow automation", "Medium", "Action-command UI + export summary"],
];

export default function IntentShadcnPage() {
  return (
    <main className="min-h-screen bg-background px-6 py-8 text-foreground">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex max-w-3xl flex-col gap-3">
            <Badge variant="secondary" className="w-fit">
              Productization review
            </Badge>
            <div className="flex flex-col gap-2">
              <h1 className="text-3xl font-semibold tracking-normal md:text-4xl">
                Productizable project map
              </h1>
              <p className="text-base text-muted-foreground">
                Ranked view of strongest demo candidates, bundle fit, and the
                packaging work needed before sales conversations.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline">
              <ClipboardListIcon data-icon="inline-start" />
              Review gaps
            </Button>
            <Button>
              Build demo plan
              <ArrowUpRightIcon data-icon="inline-end" />
            </Button>
          </div>
        </header>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>Top candidate</CardDescription>
              <CardTitle>Clinical Case Workspace</CardTitle>
              <CardAction>
                <CheckCircle2Icon className="size-5 text-muted-foreground" />
              </CardAction>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Ready for scripted demo
              </p>
              <Progress value={92} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Strongest bundle</CardDescription>
              <CardTitle>Decision support</CardTitle>
              <CardAction>
                <BoxesIcon className="size-5 text-muted-foreground" />
              </CardAction>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Combines case, evidence, and probability
              </p>
              <Progress value={86} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Packaging focus</CardDescription>
              <CardTitle>Demo narrative</CardTitle>
              <CardAction>
                <PackageCheckIcon className="size-5 text-muted-foreground" />
              </CardAction>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Convert capability into buyer story
              </p>
              <Progress value={74} />
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="projects" className="flex flex-col gap-4">
          <TabsList>
            <TabsTrigger value="projects">Projects</TabsTrigger>
            <TabsTrigger value="bundles">Bundles</TabsTrigger>
            <TabsTrigger value="work">Packaging work</TabsTrigger>
          </TabsList>

          <TabsContent value="projects">
            <Card>
              <CardHeader>
                <CardTitle>Project readiness</CardTitle>
                <CardDescription>
                  Prioritized candidates with bundle fit and packaging gaps.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Project</TableHead>
                      <TableHead>Score</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Packaging gap</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {projects.map((project) => (
                      <TableRow key={project.name}>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <span className="font-medium">
                              {project.name}
                            </span>
                            <span className="text-muted-foreground">
                              {project.bundle}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>{project.score}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{project.status}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {project.gap}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="bundles">
            <Card>
              <CardHeader>
                <CardTitle>Bundle strength</CardTitle>
                <CardDescription>
                  Which combinations are easiest to explain and sell.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Bundle</TableHead>
                      <TableHead>Strength</TableHead>
                      <TableHead>Composition</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {bundleRows.map(([bundle, strength, composition]) => (
                      <TableRow key={bundle}>
                        <TableCell className="font-medium">{bundle}</TableCell>
                        <TableCell>{strength}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {composition}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="work">
            <Card>
              <CardHeader>
                <CardTitle>Packaging checklist</CardTitle>
                <CardDescription>
                  Work needed before demos or sales conversations.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-3">
                {[
                  "Write buyer-facing demo script",
                  "Define bundle boundaries",
                  "Create reusable sample data",
                ].map((item) => (
                  <div
                    key={item}
                    className="flex min-h-24 flex-col justify-between rounded-md border bg-muted/30 p-4 text-sm"
                  >
                    <span>{item}</span>
                    <Separator />
                    <Badge variant="secondary" className="w-fit">
                      Required
                    </Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </section>
    </main>
  );
}
