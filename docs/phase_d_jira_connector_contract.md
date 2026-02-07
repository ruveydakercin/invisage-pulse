\# Phase D — Jira Connector Raw Row Contract (MVP)



Amaç:

\- Jira’dan veri çekip CSV ingestion hattındaki gibi "raw rows" üretmek.

\- Validation / ImportError / row\_status / normalize mevcut Phase C altyapısıyla aynı kalacak.



\## Raw Row Types (MVP)



Jira’dan 4 tip raw row üreteceğiz:



\### 1) jira\_project

Project upsert için minimum alanlar:

\- source: "jira"

\- row\_type: "jira\_project"

\- project\_key: string (örn: "THOR")

\- project\_name: string

\- jira\_project\_id: string/int (Jira internal id, varsa)

\- fetched\_at: ISO datetime (UTC)



\### 2) jira\_user

Resource upsert için minimum alanlar:

\- source: "jira"

\- row\_type: "jira\_user"

\- account\_id: string (Jira Cloud için kritik)

\- display\_name: string

\- email: string? (Jira izin verirse)

\- active: boolean?

\- fetched\_at: ISO datetime (UTC)



\### 3) jira\_issue

WorkItem upsert için minimum alanlar:

\- source: "jira"

\- row\_type: "jira\_issue"

\- project\_key: string

\- issue\_key: string (örn: "THOR-123")

\- issue\_type: string (Story/Bug/Task)

\- summary: string

\- status: string

\- created\_at: ISO datetime

\- updated\_at: ISO datetime

\- assignee\_account\_id: string? (yoksa null)

\- reporter\_account\_id: string? (yoksa null)

\- original\_estimate\_seconds: int? (yoksa null)

\- time\_spent\_seconds: int? (yoksa null)

\- fetched\_at: ISO datetime (UTC)



\### 4) jira\_worklog

TimeEntry insert için minimum alanlar:

\- source: "jira"

\- row\_type: "jira\_worklog"

\- project\_key: string

\- issue\_key: string

\- worklog\_id: string/int

\- author\_account\_id: string

\- started\_at: ISO datetime

\- time\_spent\_seconds: int

\- comment: string? (opsiyonel)

\- fetched\_at: ISO datetime (UTC)



\## MVP Normalization Expectations



\- jira\_project -> Project upsert (project\_key, name)

\- jira\_user    -> Resource upsert (external\_id=account\_id, display\_name)

\- jira\_issue   -> WorkItem upsert (external\_id=issue\_key, project\_key, status, type, summary, estimates)

\- jira\_worklog -> TimeEntry insert (external\_id=worklog\_id, resource/account\_id, issue\_key, started\_at, seconds)



\## Validation Rules (minimum)



\- jira\_project: project\_key boş olamaz

\- jira\_user: account\_id boş olamaz

\- jira\_issue: project\_key ve issue\_key boş olamaz

\- jira\_worklog: issue\_key + worklog\_id + author\_account\_id + started\_at + time\_spent\_seconds zorunlu



Not:

\- Jira connector yalnızca raw rows basar.

\- Normalize işlemi mevcut /imports/{batch\_id}/normalize ile yapılır.

