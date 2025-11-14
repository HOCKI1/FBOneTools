using System;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using BFBC2Shared.Data;
using Microsoft.Win32;

namespace BFBC2Shared.Functions
{
    public class Python
    {
        public static async Task ExecuteScript(string script)
        {
            using (var process = Process.Start(SharedSettings.PathToPython, "\"" + script + "\""))
                await Task.Run(() => process.WaitForExit());
        }

        public static async Task ExecuteScript(string script, string target)
        {
            using (var process = Process.Start(SharedSettings.PathToPython, "\"" + script + "\" \"" + target + "\""))
                await Task.Run(() => process.WaitForExit());
        }

        public static async Task ExecuteScript(string script, string target, string destination)
        {
            using (var process = Process.Start(SharedSettings.PathToPython, "\"" + script + "\" \"" + target + "\" \"" + destination + "\""))
                await Task.Run(() => process.WaitForExit());
        }

        public static string ChangePath()
        {
            try
            {
                var ofd = new OpenFileDialog();
                ofd.Filter = "exe file (.exe)|*.exe";
                ofd.Title = "Select pythonw.exe...";

                if (ofd.ShowDialog() == true)
                {
                    string path = ofd.FileName;

                    if (path.EndsWith("pythonw.exe"))
                    {
                        SharedSettings.PathToPython = path;

                        return path;
                    }
                    else
                    {
                        path = Path.GetDirectoryName(path) + @"\pythonw.exe";

                        if (File.Exists(path))
                        {
                            SharedSettings.PathToPython = path;

                            return path;
                        }
                        else
                        {
                            return String.Empty;
                        }
                    }
                }

                return String.Empty;
            }
            catch (Exception ex)
            {
                Log.Error(ex.ToString());

                return String.Empty;
            }
        }

        public static bool CheckVersion()
        {
            try
            {
                var processInfo = new ProcessStartInfo
                {
                    FileName = SharedSettings.PathToPython.Replace("pythonw.exe", "python.exe"),
                    Arguments = "--version",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                using (var process = Process.Start(processInfo))
                {
                    string output = process.StandardOutput.ReadToEnd();
                    string error = process.StandardError.ReadToEnd();
                    process.WaitForExit();

                    string versionInfo = output + error;

                    return versionInfo.Contains("Python 3.11");
                }
            }
            catch (Exception ex)
            {
                Log.Error(ex.ToString());
                return false;
            }
        }
    }
}
