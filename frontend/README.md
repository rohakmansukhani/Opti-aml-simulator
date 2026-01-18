# Frontend Components & Pages

This directory contains the Next.js frontend application for the SAS Sandbox Simulator.

## 📁 Structure

```
frontend/src/
├── app/                    # Next.js 13+ App Router
│   ├── page.tsx           # Landing & Auth page
│   ├── dashboard/         # Main dashboard
│   │   ├── page.tsx       # Dashboard home
│   │   └── reports/       # Simulation reports
│   └── layout.tsx         # Root layout
├── components/            # Reusable React components
│   └── TTLCountdown.tsx   # Data expiry countdown
├── lib/                   # Utilities & API client
│   └── api.ts             # Axios instance
└── store/                 # State management
    └── useSessionStore.ts # Session/auth state
```

## 🎨 Key Pages

### 1. Landing/Auth Page (`app/page.tsx`)
**Features:**
- Magic link authentication (Supabase)
- Enterprise database connection
- PostgreSQL URL validation
- Inline error handling

**User Flow:**
1. Enter email → Receive magic link
2. Click link → Auto-login
3. Connect to database OR use demo data
4. Redirect to dashboard

---

### 2. Dashboard (`app/dashboard/page.tsx`)
**Features:**
- Statistics cards (risk score, alerts, coverage)
- Recent simulations list
- Run simulation dialog (3-step wizard)
- Field mapping interface
- Real-time updates

**Simulation Dialog Steps:**
1. **SELECT:** Choose scenarios
2. **CONFIG:** Set date range
3. **MAPPING:** Map missing fields (if needed)

---

### 3. Reports (`app/dashboard/reports/page.tsx`)
**Features:**
- Simulation results table
- Alert filtering & sorting
- Excel export
- Risk analysis visualization
- Exclusion logs

---

## 🧩 Components

### TTLCountdown
**File:** `components/TTLCountdown.tsx`

**Purpose:** Displays data expiry countdown with extension option.

**Props:**
```typescript
{
    expiresAt: string;      // ISO timestamp
    uploadId: string;       // Upload ID
    onExtend?: () => void;  // Extension callback
}
```

**States:**
- **Active** (> 6h remaining): Blue, informational
- **Warning** (< 6h remaining): Amber, shows "Extend +24h" button
- **Expired**: Red, data deleted message

---

## 🔄 State Management

### Session Store (`store/useSessionStore.ts`)
**Type:** Zustand store

**State:**
```typescript
{
    isConnected: boolean;
    dbUrl: string | null;
    uploadMetadata: { uploadId: string; expiresAt: string } | null;
}
```

**Actions:**
- `setConnected(url: string)` - Mark as connected
- `disconnect()` - Clear session
- `setUploadMetadata(data)` - Store upload info

---

## 🌐 API Integration

### API Client (`lib/api.ts`)
```typescript
import axios from 'axios';

export const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json'
    }
});
```

**Usage:**
```typescript
const response = await api.post('/api/simulation/run', {
    scenarios: ['ICICI_01'],
    run_type: 'baseline'
});
```

---

## 🎨 Styling

### Technology Stack:
- **Tailwind CSS** - Utility-first styling
- **Material-UI** - Dialog, Button, CircularProgress components
- **Framer Motion** - Animations & transitions
- **Lucide React** - Icon library

### Design System:
```css
/* Primary Colors */
--blue-600: #2563eb;
--slate-900: #0f172a;

/* Status Colors */
--green-600: #16a34a;  /* Success */
--amber-600: #d97706;  /* Warning */
--red-600: #dc2626;    /* Error */
```

---

## 🔐 Authentication Flow

```
User enters email
    ↓
POST /auth/magic-link (Supabase)
    ↓
Email sent with token
    ↓
User clicks link
    ↓
Token validated
    ↓
Session created (JWT)
    ↓
Redirect to /dashboard
```

**Session Storage:**
- JWT token in `localStorage`
- Session state in Zustand store
- Auto-redirect if not authenticated

---

## 📊 Data Flow

```
User Action (UI)
    ↓
React Component
    ↓
API Call (axios)
    ↓
Backend Endpoint
    ↓
Response
    ↓
State Update (Zustand)
    ↓
UI Re-render
```

---

## 🧪 Development

### Run Locally:
```bash
cd frontend
npm install
npm run dev
```

### Build for Production:
```bash
npm run build
npm start
```

### Environment Variables:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

---

## 🚀 Performance

### Optimizations:
1. **Next.js Image Optimization** - Automatic image optimization
2. **Code Splitting** - Route-based code splitting
3. **Static Generation** - Pre-render where possible
4. **API Response Caching** - Cache dashboard stats (60s)

### Bundle Size:
- Initial JS: ~150KB (gzipped)
- Total Page Weight: ~300KB
- First Contentful Paint: < 1.5s

---

## 🎯 User Experience

### Error Handling:
- Inline error messages (no `alert()`)
- Toast notifications for success
- Loading states for async operations
- Graceful degradation

### Accessibility:
- Semantic HTML
- ARIA labels
- Keyboard navigation
- Screen reader support

---

## 📱 Responsive Design

### Breakpoints:
```css
sm: 640px   /* Mobile */
md: 768px   /* Tablet */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large Desktop */
```

### Mobile-First:
All components designed mobile-first, enhanced for larger screens.

---

## 🔗 Key Dependencies

```json
{
    "next": "14.x",
    "react": "18.x",
    "axios": "1.x",
    "zustand": "4.x",
    "@mui/material": "5.x",
    "framer-motion": "10.x",
    "lucide-react": "latest"
}
```
