import React from "react";
import { Box, Typography } from "@mui/material";

function App() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
        backgroundColor: "#f5f5f5",
      }}
    >
      <Typography variant="h3" component="h1" gutterBottom>
        Hello World
      </Typography>
      <Typography variant="body1">
        This is your first Material UI component in Vite React!
      </Typography>
    </Box>
  );
}

export default App;
