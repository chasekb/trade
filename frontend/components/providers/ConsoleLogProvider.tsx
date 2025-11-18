'use client';

import { useEffect } from 'react';
import { apiClient } from '@/lib/api';

const ConsoleLogProvider = ({ children }: { children: React.ReactNode }) => {
  useEffect(() => {
    const originalConsoleLog = console.log;

    console.log = (...args: any[]) => {
      // Call the original console.log so that messages still appear in the browser console
      originalConsoleLog.apply(console, args);

      // Format the arguments into a string to send to the backend
      const message = args.map(arg => {
        if (typeof arg === 'object' && arg !== null) {
          try {
            return JSON.stringify(arg);
          } catch (error) {
            return 'Unserializable object';
          }
        }
        return String(arg);
      }).join(' ');

      // Send the log message to the backend
      apiClient.logMessage(message).catch(error => {
        originalConsoleLog('Failed to send log message to backend:', error);
      });
    };

    // Cleanup function to restore the original console.log when the component unmounts
    return () => {
      console.log = originalConsoleLog;
    };
  }, []);

  return <>{children}</>;
};

export default ConsoleLogProvider;
