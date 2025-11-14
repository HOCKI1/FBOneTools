using System;
using System.IO;

namespace BFBC2Shared.Data
{
    public class SharedSettings
    {
        public static string PathToPython { get; set; } =
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "python", "pythonw.exe");
    }
}
