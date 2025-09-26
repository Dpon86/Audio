import React, { useState } from "react";
import { useNavigate } from 'react-router-dom';
import '../../static/CSS/Header.css'; // Make sure to create this CSS file for styling

const Header = () => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [userDetailsOpen, setUserDetailsOpen] = useState(false);
  const navigate = useNavigate();

  const toggleMenu = () => setMenuOpen(!menuOpen);
  const toggleUserDetails = () => setUserDetailsOpen(!userDetailsOpen);

  const handleSignOut = () => {
    sessionStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <>
      <header className="Hd-header">
        <div className="Hd-hamburger-menu" onClick={toggleMenu}>
          <div className="Hd-line"></div>
          <div className="Hd-line"></div>
          <div className="Hd-line"></div>
        </div>
        <div className="Hd-header-title-container">
          <div className="Hd-title">Precise Audio Detection</div>
        </div>
        <div className="Hd-header-right">
          <button onClick={toggleUserDetails} className="Hd-User-button">Show user details</button>
          <button onClick={handleSignOut} className="Hd-sign-out-button">Exit</button>
        </div>
      </header>
      <Menu isOpen={menuOpen} toggle={toggleMenu} navigate={navigate} />
      <Modal isOpen={userDetailsOpen} toggle={toggleUserDetails}>
        <UserDetails />
      </Modal>
    </>
  );
};

const Menu = ({ isOpen, toggle, navigate }) => (
  <div className={`Hd-sidebar-bottom ${isOpen ? 'open' : ''}`}>
    <ul>
      <li>
        <a
          href="/AudioUpload"
          onClick={e => {
            e.preventDefault();
            toggle();
            navigate('/AudioUpload');
          }}
        >
          Audio Page
        </a>
      </li>
            <li>
        <a
          href="/PDFAnalysis"
          onClick={e => {
            e.preventDefault();
            toggle();
            navigate('/PDFAnalysis');
          }}
        >
          PDF upload Page
        </a>
      </li>
      <li>
        <a
          href="/EditPage"
          onClick={e => {
            e.preventDefault();
            toggle();
            navigate('/EditPage');
          }}
        >
          Edit Page
        </a>
      </li>
      <li>
        <a
          href="/login"
          onClick={e => {
            e.preventDefault();
            toggle();
            navigate('/login');
          }}
        >
          Logout
        </a>
      </li>
    </ul>
  </div>
);

const Modal = ({ isOpen, toggle, children }) => {
  if (!isOpen) return null;
  return (
    <div className='Hd-modal'>
      <div className='Hd-modal-content'>
        <button onClick={toggle}>Close</button>
        {children}
      </div>
    </div>
  );
};

const UserDetails = () => (
  <div>
    <p>Username: DemoUser</p>
    <p>Name: Demo Name</p>
  </div>
);

export default Header;