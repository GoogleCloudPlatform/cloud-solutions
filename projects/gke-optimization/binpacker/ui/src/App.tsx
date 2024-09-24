/**
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
import routes from './components/Routes';
import { useRoutes } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.min.css';
import './styles/CustomToast.css';

const theme = createTheme({
  palette: {
    mode: 'light',
  },
});

function App() {
  const contents = useRoutes(routes);
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ToastContainer style={{ width: '500px' }} />
      {contents}
    </ThemeProvider>
  );
}

export default App;
