# Contextual AI Dashboard -   React Client

A modern React dashboard application built with TypeScript, Tailwind CSS, and
shadcn/ui components featuring a professional layout with top header, left
sidebar navigation, and AI chat integration.

## 🚀 Quick Start

### Prerequisites

-   Node.js 16.x or higher
-   npm or yarn package manager

### Installation & Setup

-   **Navigate to the client directory:**

```bash
cd client
```

-   **Install dependencies:**

```bash
npm install
```

-   **Start the development server:**

```bash
npm start
```

-   **Open your browser:** Navigate to
  [http://localhost:3000](http://localhost:3000) to view the dashboard.

## 🎨 Dashboard Features

### Layout Components

-   **📍 Top Header**: Search bar, notifications, settings, chat toggle, and user
  profile
-   **📂 Left Sidebar**: Navigation menu with icons, badges, and upgrade prompt
-   **📊 Main Content**: Dynamic content area that changes based on navigation
  selection
-   **💬 Chat Drawer**: AI assistant chat interface that slides in from the right

### Dashboard Sections

-   **Dashboard**: Overview with stats, charts, recent activity, and quick actions
-   **Analytics**: Data visualization and metrics (placeholder)
-   **Data Sources**: Data management interface (placeholder)
-   **AI Models**: Machine learning model management (placeholder)
-   **Monitoring**: System monitoring and health checks (placeholder)
-   **Automation**: Workflow automation tools (placeholder)
-   **Reports**: Report generation and management (placeholder)
-   **Users**: User management interface (placeholder)
-   **Settings**: Application settings (placeholder)

### Interactive Features

-   ✅ Responsive navigation with active state highlighting
-   ✅ Real-time chat interface with message history
-   ✅ Notification badges and system status indicators
-   ✅ Quick action buttons and system health monitoring
-   ✅ Dark/light mode support (built into shadcn/ui)

## 📦 What's Included

### Tech Stack

-   ⚛️ **React 18** with TypeScript
-   🎨 **Tailwind CSS** for styling
-   🧩 **shadcn/ui** component library
-   🎯 **Lucide React** for beautiful icons
-   🛠️ **CRACO** for configuration overrides
-   📦 **Path aliases** (@/ imports)

### Key Components

-   `Header.tsx` -   Top navigation with search, notifications, and user profile
-   `Sidebar.tsx` -   Left navigation menu with route management
-   `DashboardContent.tsx` -   Main content area with section routing
-   `ChatDrawer.tsx` -   AI chat interface with message history
-   `ui/` -   shadcn/ui component library (Button, Card, Sheet, Input, Avatar,
  Badge)

## 🛠️ Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in interactive watch mode.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the
best performance.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can
`eject` at any time.

## 🎨 Adding shadcn/ui Components

You can add more components from the shadcn/ui library:

```bash
# Add a dialog component
npx shadcn@latest add dialog

# Add a table component
npx shadcn@latest add table

# Add a form component
npx shadcn@latest add form

# See all available components
npx shadcn@latest add
```

## 📁 Project Structure

```text
client/
├── public/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn/ui components
│   │   ├── Header.tsx       # Top navigation header
│   │   ├── Sidebar.tsx      # Left navigation sidebar
│   │   ├── DashboardContent.tsx # Main content area
│   │   └── ChatDrawer.tsx   # AI chat interface
│   ├── lib/
│   │   └── utils.ts         # Utility functions
│   ├── App.tsx              # Main application layout
│   ├── index.tsx
│   └── index.css            # Global styles & Tailwind directives
├── components.json          # shadcn/ui configuration
├── tailwind.config.js       # Tailwind CSS configuration
├── tsconfig.json            # TypeScript configuration
└── craco.config.js          # CRACO configuration for path aliases
```

## 🎯 Usage Examples

### Navigation State Management

```tsx
const [activeItem, setActiveItem] = useState('dashboard');

// Pass to sidebar for highlighting
<Sidebar activeItem={activeItem} onItemSelect={setActiveItem} />

// Pass to content for routing
<DashboardContent activeItem={activeItem} />
```

### Chat Integration

```tsx
const [chatOpen, setChatOpen] = useState(false);

// Toggle from header
<Header onChatToggle={() => setChatOpen(!chatOpen)} chatOpen={chatOpen} />

// Drawer component
<ChatDrawer open={chatOpen} onOpenChange={setChatOpen} />
```

### Adding New Dashboard Sections

To add a new section to the dashboard:

-   **Add to navigation** in `Sidebar.tsx`:

```tsx
{ id: 'new-section', label: 'New Section', icon: <Icon className="h-4 w-4" /> }
```

-   **Add route handling** in `DashboardContent.tsx`:

```tsx
case 'new-section':
  return renderNewSection();
```

-   **Create content component**:

```tsx
const renderNewSection = () => (
  <div className="space-y-6">
    <Card>
      <CardHeader>
        <CardTitle>New Section</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Your content here */}
      </CardContent>
    </Card>
  </div>
);
```

## 🎨 Theming

The dashboard uses a comprehensive design system with CSS variables:

### Color System

-   **Background**: `bg-background`, `bg-card`, `bg-muted`
-   **Text**: `text-foreground`, `text-muted-foreground`
-   **Interactive**: `text-primary`, `text-secondary`
-   **Status**: `text-destructive`, badges with custom colors
-   **Borders**: `border-border`, `border-input`

### Layout Classes

-   **Spacing**: Consistent `space-y-6`, `gap-6` patterns
-   **Grid**: Responsive grid layouts with
  `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`
-   **Flexbox**: `flex`, `items-center`, `justify-between` for component layouts

## 📱 Responsive Design

The dashboard is fully responsive with breakpoints:

-   **Mobile**: Single column layout, collapsible navigation
-   **Tablet**: Two-column grids, condensed header
-   **Desktop**: Full layout with all components visible

## 🧪 Demo Features

The dashboard includes demo data and functionality:

-   Sample dashboard statistics with trend indicators
-   Mock chat messages with AI responses
-   System status indicators and recent activity feeds
-   Quick action buttons and navigation badges

## 📚 Resources

-   [React Documentation](https://reactjs.org/)
-   [TypeScript Handbook](https://www.typescriptlang.org/docs/)
-   [Tailwind CSS Documentation](https://tailwindcss.com/docs)
-   [shadcn/ui Documentation](https://ui.shadcn.com/)
-   [Lucide React Icons](https://lucide.dev/)
-   [CRACO Documentation](https://craco.js.org/)

## 📝 License

This project is licensed under the MIT License.
