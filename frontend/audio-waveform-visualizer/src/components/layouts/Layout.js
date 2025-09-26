import React from "react";
import Header from "../header/Header";

const Layout = ({ children }) => (
  <>
    <Header />
    <main>{children}</main>
  </>
);

export default Layout;