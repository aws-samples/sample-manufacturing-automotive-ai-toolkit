# Fleet Discovery Studio - Frontend

Reference architecture for building AI-powered fleet data discovery interfaces using Next.js, React, and AWS services.

## Overview

This frontend demonstrates patterns for:
- Semantic search over vehicle telemetry data
- Real-time analytics dashboards
- Multi-camera video playback
- AWS Cognito authentication
- Integration with FastAPI backends

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **UI**: React 19, Tailwind CSS 4, Radix UI
- **Charts**: Recharts
- **Auth**: AWS Amplify (Cognito)
- **Animation**: Framer Motion

## Project Structure

```
src/
├── app/                   # Next.js App Router pages
│   ├── page.tsx           # Fleet Command (main dashboard)
│   ├── analytics/         # ODD coverage analytics
│   ├── forensic/          # Scene detail view
│   ├── login/             # Cognito authentication
│   ├── pipeline/          # Processing pipeline status
│   ├── search/            # Semantic search interface
│   └── settings/          # Configuration
├── components/
│   ├── auth/              # Auth provider, protected routes
│   ├── fleet/             # Scene cards, search bar, filters
│   ├── forensic/          # Video player, agent analysis
│   ├── layout/            # Dashboard shell, sidebar, header
│   ├── search/            # Search results display
│   ├── ui/                # Reusable UI primitives
│   └── upload/            # ROS bag upload interface
├── hooks/                 # Data fetching hooks
│   ├── useFleetData.ts    # Fleet overview & stats
│   ├── useSearch.ts       # Semantic search
│   ├── useSceneDetail.ts  # Individual scene data
│   ├── useAnalytics.ts    # Coverage analytics
│   └── useAuth.ts         # Authentication state
├── lib/                   # Utilities
│   ├── auth-config.ts     # Amplify configuration
│   └── utils.ts           # Helper functions
└── types/                 # TypeScript definitions
```

## Getting Started

### Prerequisites

- Node.js >= 20
- npm or yarn

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Environment Variables

Create `.env.local`:

```env
# API endpoint (defaults to /api for same-origin)
NEXT_PUBLIC_API_URL=/api

# AWS Cognito (optional - for authentication)
NEXT_PUBLIC_COGNITO_USER_POOL_ID=us-west-2_xxxxx
NEXT_PUBLIC_COGNITO_CLIENT_ID=xxxxx
NEXT_PUBLIC_AWS_REGION=us-west-2
```

## Authentication & User Management

Self-registration is disabled. Users are provisioned by an administrator.

### Initial user (via deploy script)

The main deploy script creates the first user automatically:

```bash
./deploy_cdk.sh --auth-user agweber@amazon.com --auth-password '1234Qwer!!' --skip-nag
```

The `--auth-user` and `--auth-password` flags are passed as `AUTH_USER` / `AUTH_PASSWORD` environment variables to CDK, which provisions a Lambda-backed custom resource to call `AdminCreateUser` + `AdminSetUserPassword` on the Cognito User Pool.

### Adding users after deployment

Use the AWS CLI to create additional users against the deployed Cognito User Pool:

```bash
# Find the User Pool ID from stack outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name MA3TMainStack \
  --query "Stacks[0].Outputs[?contains(OutputKey,'UserPool')].OutputValue" \
  --output text --region us-west-2)

# Create a new user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --region us-west-2

# Set a permanent password (skips the force-change-password flow)
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --password 'SecurePass123!' \
  --permanent \
  --region us-west-2
```

Password requirements: 8+ characters, uppercase, lowercase, digit, and symbol.

## Key Patterns

### API Integration

All API calls use relative paths through hooks:

```typescript
// hooks/useFleetData.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api"

export function useFleetStats() {
  const [stats, setStats] = useState<FleetStats | null>(null)
  
  useEffect(() => {
    fetch(`${API_BASE_URL}/stats/overview`)
      .then(res => res.json())
      .then(setStats)
  }, [])
  
  return { stats }
}
```

### Protected Routes

Wrap pages requiring authentication:

```tsx
// app/page.tsx
import ProtectedRoute from "@/components/auth/ProtectedRoute"

export default function Home() {
  return (
    <ProtectedRoute>
      <DashboardLayout>
        <FleetCommand />
      </DashboardLayout>
    </ProtectedRoute>
  )
}
```

### Adding New Pages

1. Create route in `app/[route]/page.tsx`
2. Add data hook in `hooks/use[Feature].ts`
3. Create components in `components/[feature]/`

Example:

```tsx
// app/vehicles/page.tsx
"use client"
import { useVehicles } from "@/hooks/useVehicles"
import DashboardLayout from "@/components/layout/DashboardLayout"

export default function VehiclesPage() {
  const { vehicles, loading } = useVehicles()
  
  return (
    <DashboardLayout>
      {/* Your content */}
    </DashboardLayout>
  )
}
```

### Adding API Endpoints

Frontend expects these backend routes (see `../api/`):

| Route | Method | Description |
|-------|--------|-------------|
| `/stats/overview` | GET | Fleet statistics |
| `/fleet/overview` | GET | Paginated scene list |
| `/scene/{id}` | GET | Scene details |
| `/scene/{id}/video` | GET | Video stream |
| `/search` | POST | Semantic search |
| `/analytics/*` | GET | Coverage analytics |

## Customization

### Theming

CSS variables in `app/globals.css`:

```css
:root {
  --cyber-blue: #00D4FF;
  --deep-charcoal: #1a1a2e;
  --slate-grey: #64748b;
  --pure-white: #ffffff;
}
```

### UI Components

Reusable primitives in `components/ui/`:
- `Button` - Styled button with variants
- `Card` - Container component
- `Badge` - Status indicators
- `InfoTooltip` - Contextual help

## Build & Deploy

```bash
# Production build
npm run build

# Start production server
npm start
```

The frontend is designed to be deployed behind CloudFront with the API at `/api/*`.

## License

MIT - See repository root for details.
