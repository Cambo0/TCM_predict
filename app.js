// App.js
import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Switch, Redirect } from 'react-router-dom';
import Login from './components/Login';
import Register from './components/Register';
import PrescriptionForm from './components/PrescriptionForm';
import DiagnosisHistory from './components/DiagnosisHistory';
import AdminInterface from './components/AdminInterface';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  return (
    <Router>
      <div className="App">
        <Switch>
          <Route path="/login">
            <Login setIsAuthenticated={setIsAuthenticated} setIsAdmin={setIsAdmin} />
          </Route>
          <Route path="/register">
            <Register />
          </Route>
          <PrivateRoute path="/predict" component={PrescriptionForm} isAuthenticated={isAuthenticated} />
          <PrivateRoute path="/history" component={DiagnosisHistory} isAuthenticated={isAuthenticated} />
          <AdminRoute path="/admin" component={AdminInterface} isAuthenticated={isAuthenticated} isAdmin={isAdmin} />
          <Redirect from="/" to="/login" />
        </Switch>
      </div>
    </Router>
  );
}

function PrivateRoute({ component: Component, isAuthenticated, ...rest }) {
  return (
    <Route
      {...rest}
      render={(props) =>
        isAuthenticated ? (
          <Component {...props} />
        ) : (
          <Redirect to="/login" />
        )
      }
    />
  );
}

function AdminRoute({ component: Component, isAuthenticated, isAdmin, ...rest }) {
  return (
    <Route
      {...rest}
      render={(props) =>
        isAuthenticated && isAdmin ? (
          <Component {...props} />
        ) : (
          <Redirect to="/login" />
        )
      }
    />
  );
}

export default App;

// components/Login.js
import React, { useState } from 'react';
import axios from 'axios';
import { useHistory } from 'react-router-dom';

const Login = ({ setIsAuthenticated, setIsAdmin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const history = useHistory();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('/login', { username, password });
      localStorage.setItem('token', response.data.access_token);
      setIsAuthenticated(true);
      // You would typically decode the JWT to get user info including admin status
      setIsAdmin(true); // This is a placeholder. In reality, you'd check the token
      history.push('/predict');
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      <button type="submit">Login</button>
    </form>
  );
};

export default Login;

// components/Register.js
import React, { useState } from 'react';
import axios from 'axios';
import { useHistory } from 'react-router-dom';

const Register = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const history = useHistory();
  
    const handleSubmit = async (e) => {
      e.preventDefault();
      try {
        await axios.post('/register', { username, password });
        history.push('/login');
      } catch (error) {
        console.error('Registration failed:', error);
      }
    };
  
    return (
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="Username"
          required
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          required
        />
        <button type="submit">Register</button>
      </form>
    );
  };
  
  export default Register;
  
  // components/PrescriptionForm.js
  import React, { useState } from 'react';
  import axios from 'axios';
  
  const PrescriptionForm = () => {
    const [prescription, setPrescription] = useState('');
    const [predictions, setPredictions] = useState([]);
    const [error, setError] = useState('');
  
    const handleSubmit = async (e) => {
      e.preventDefault();
      try {
        const response = await axios.post('/predict', { prescription }, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        setPredictions(response.data.predictions);
      } catch (err) {
        setError('An error occurred. Please try again.');
      }
    };
  
    return (
      <div>
        <form onSubmit={handleSubmit}>
          <textarea 
            value={prescription} 
            onChange={(e) => setPrescription(e.target.value)}
            placeholder="Enter prescription here..."
          />
          <button type="submit">Predict Disease</button>
        </form>
        {error && <p>{error}</p>}
        {predictions.length > 0 && (
          <ul>
            {predictions.map((pred, index) => (
              <li key={index}>{pred.disease}: {(pred.probability * 100).toFixed(2)}%</li>
            ))}
          </ul>
        )}
      </div>
    );
  };
  
  export default PrescriptionForm;
  
  // components/DiagnosisHistory.js
  import React, { useState, useEffect } from 'react';
  import axios from 'axios';
  
  const DiagnosisHistory = () => {
    const [history, setHistory] = useState([]);
  
    useEffect(() => {
      fetchDiagnosisHistory();
    }, []);
  
    const fetchDiagnosisHistory = async () => {
      try {
        const response = await axios.get('/diagnosis-history', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        });
        setHistory(response.data);
      } catch (error) {
        console.error('Error fetching diagnosis history:', error);
      }
    };
  
    return (
      <div>
        <h2>Diagnosis History</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Prescription</th>
              <th>Predicted Disease</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {history.map((log) => (
              <tr key={log.id}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td>{log.prescription}</td>
                <td>{log.predicted_disease}</td>
                <td>{(log.confidence * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };
  
  export default DiagnosisHistory;
  
  // components/AdminInterface.js
  import React, { useState, useEffect } from 'react';
  import axios from 'axios';
  
  const AdminInterface = () => {
    const [herbs, setHerbs] = useState([]);
    const [diseases, setDiseases] = useState([]);
    const [newHerb, setNewHerb] = useState({ name: '', description: '' });
    const [newDisease, setNewDisease] = useState({ name: '', description: '' });
  
    useEffect(() => {
      fetchHerbs();
      fetchDiseases();
    }, []);
  
    const fetchHerbs = async () => {
      const response = await axios.get('/admin/herbs', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      setHerbs(response.data);
    };
  
    const fetchDiseases = async () => {
      const response = await axios.get('/admin/diseases', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      setDiseases(response.data);
    };
  
    const addHerb = async (e) => {
      e.preventDefault();
      await axios.post('/admin/herbs', newHerb, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      setNewHerb({ name: '', description: '' });
      fetchHerbs();
    };
  
    const addDisease = async (e) => {
      e.preventDefault();
      await axios.post('/admin/diseases', newDisease, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      setNewDisease({ name: '', description: '' });
      fetchDiseases();
    };
  
    return (
      <div>
        <h2>Admin Interface</h2>
        <div>
          <h3>Add New Herb</h3>
          <form onSubmit={addHerb}>
            <input
              type="text"
              value={newHerb.name}
              onChange={(e) => setNewHerb({ ...newHerb, name: e.target.value })}
              placeholder="Herb Name"
            />
            <input
              type="text"
              value={newHerb.description}
              onChange={(e) => setNewHerb({ ...newHerb, description: e.target.value })}
              placeholder="Description"
            />
            <button type="submit">Add Herb</button>
          </form>
        </div>
        <div>
          <h3>Add New Disease</h3>
          <form onSubmit={addDisease}>
            <input
              type="text"
              value={newDisease.name}
              onChange={(e) => setNewDisease({ ...newDisease, name: e.target.value })}
              placeholder="Disease Name"
            />
            <input
              type="text"
              value={newDisease.description}
              onChange={(e) => setNewDisease({ ...newDisease, description: e.target.value })}
              placeholder="Description"
            />
            <button type="submit">Add Disease</button>
          </form>
        </div>
        {/* Add lists to display and edit existing herbs and diseases */}
      </div>
    );
  };
  
  export default AdminInterface;